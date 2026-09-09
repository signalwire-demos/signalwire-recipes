"""Prove the claim without a network.

Claim: one POST creates a subproject, and a second creates an API token bound
to it through `subproject_id` with exactly the permissions you list. The
spec's permission enum is the whole vocabulary, and `management` is not in
this token's list.

Proof: the HTTP layer is a recorder that answers the project create with an
id and the token create with a token. `create_tenant`, called with a
permission list that is not the default, makes two POSTs in order to the
documented paths. The project body is exactly `name` and
`force_https_requests`. The token body is exactly `name`, the list passed, and
a `subproject_id` equal to the id the first response carried. Every permission
is in the spec's enum. The spec's required fields are exactly `name` on the
project and `name` plus `permissions` on the token, its 201 project response
carries the fields the prose names, and it documents no GET for tokens.
Expected values live here, not in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
})

import verifylib as V  # noqa: E402

PROJECTS, TOKENS = "/api/projects", "/api/project/tokens"
PID = "9d2c1b0a-3e4f-4a5b-8c7d-6e5f4a3b2c1d"
TID = "0a1b2c3d-4e5f-4a6b-9c8d-7e6f5a4b3c2d"
SECRET = "PT-verifier-only-not-a-real-token"
# not app.py's default, so a helper that ignored its argument would fail
PERMS = ["messaging", "calling", "numbers"]


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def body_schema(spec, path):
    op = spec["paths"][path]["post"]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def response_props(spec, path, code):
    op = spec["paths"][path]["post"]
    return deref(spec, op["responses"][code]["content"]["application/json"]["schema"])["properties"]


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[
        {"id": PID, "name": "Ridgeline Cycles"},
        {"id": TID, "name": "Ridgeline Cycles api", "permissions": list(PERMS), "token": SECRET},
    ])
    recipe.http = rec
    recipe.client.project.tokens._http = rec

    tenant = recipe.create_tenant("Ridgeline Cycles", permissions=PERMS)

    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", PROJECTS), ("POST", TOKENS)], \
        [(c["method"], c["path"]) for c in rec.calls]
    project, token = rec.calls
    assert project["body"] == {"name": "Ridgeline Cycles", "force_https_requests": True}, project
    assert token["body"] == {"name": "Ridgeline Cycles api", "permissions": PERMS,
                             "subproject_id": PID}, token
    assert tenant == {"project_id": PID, "token_id": TID, "permissions": PERMS,
                      "token": SECRET}, tenant

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", PROJECTS, project["body"])
    V.assert_documented("rest", "POST", TOKENS, token["body"])
    assert body_schema(spec, PROJECTS)["required"] == ["name"]
    assert set(body_schema(spec, TOKENS)["required"]) == {"name", "permissions"}

    # the vocabulary, and what this token leaves out of it
    perms = deref(spec, body_schema(spec, TOKENS)["properties"]["permissions"])
    enum = deref(spec, perms["items"])["enum"]
    assert set(token["body"]["permissions"]) <= set(enum), (token["body"]["permissions"], enum)
    assert set(enum) == {"calling", "chat", "datasphere", "fax", "management", "messaging",
                         "numbers", "pubsub", "storage", "tasking", "video"}, sorted(enum)

    # the response shapes the prose names, at the codes the spec gives them
    assert {"id", "subproject", "parent_project_id", "signing_key"} <= \
        set(response_props(spec, PROJECTS, "201"))
    assert {"id", "token", "permissions"} <= set(response_props(spec, TOKENS, "200"))
    # no way to read a token back, and a documented way to rotate a signing key
    assert "get" not in spec["paths"][TOKENS], list(spec["paths"][TOKENS])
    assert "get" not in spec["paths"][f"{TOKENS}/{{token_id}}"], list(spec["paths"][f"{TOKENS}/{{token_id}}"])
    rotate = spec["paths"]["/api/projects/{id}/signing-key/rotate"]["post"]
    assert rotate["summary"] == "Rotate a project's signing key", rotate["summary"]

    print(f"ok: POST {PROJECTS} name only, then POST {TOKENS} with subproject_id={PID[:8]}... "
          f"and permissions {PERMS}; the enum has eleven names and no GET reads a token back")


if __name__ == "__main__":
    main()
