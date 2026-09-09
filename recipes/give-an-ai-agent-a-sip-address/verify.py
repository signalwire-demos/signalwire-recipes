"""Prove the claim without a network.

Claim: one `POST /api/fabric/sip_addresses` with a URL-safe `name` and the
resource's `calling_handler_resource_id` gives a hosted agent a dialable SIP
URI, with `user` left to the spec's `*` default unless you set it.

Proof: with the HTTP layer replaced by a recorder, each helper call adds exactly
one POST to the documented path and the body equals the expected shape. The
required list, the `user` default, the codec and cipher defaults, the
encryption enum and the name rule are read from the vendored spec; a name the
spec would reject is refused before any request. The TypeScript surface goes
through the same seam and is held to the same bodies. Expected values live
here, not in app.py.
"""
import json
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

PATH = "/api/fabric/sip_addresses"
AGENT_ID = "0b7a2f3e-9c41-4d6e-8a52-1f0e3d2c4b5a"
NAME = "front-desk"
URI = "sip:*@front-desk.example.sip.signalwire.com"


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[
        {"id": "addr-1", "type": "sip_address", "resource_id": AGENT_ID, "name": NAME,
         "user": "*", "uri": URI, "context": "public", "encryption": "required"},
        {"id": "addr-2", "type": "sip_address", "resource_id": AGENT_ID, "name": NAME,
         "user": "reception", "uri": URI.replace("*", "reception"),
         "context": "public", "encryption": "required"},
    ])
    recipe.http = rec

    # a name the spec would reject never reaches the wire
    for bad in ("Front Desk", "front_desk", "Front-Desk", ""):
        try:
            recipe.give_address(AGENT_ID, bad)
        except ValueError as exc:
            assert "lowercase" in str(exc), exc
        else:
            raise AssertionError(f"sent an address named {bad!r}")
    assert rec.calls == [], rec.calls

    made = recipe.give_address(AGENT_ID, NAME)
    assert recipe.dial_string(made) == URI
    recipe.give_address(AGENT_ID, NAME, user="reception")
    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", PATH)] * 2

    expected = [
        {"name": NAME, "calling_handler_resource_id": AGENT_ID, "encryption": "required"},
        {"name": NAME, "calling_handler_resource_id": AGENT_ID, "encryption": "required",
         "user": "reception"},
    ]
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    op = spec["paths"][PATH]["post"]
    schema = deref(list(op["requestBody"]["content"].values())[0]["schema"])
    props = {k: deref(v) for k, v in schema["properties"].items()}
    assert set(schema["required"]) == {"name", "calling_handler_resource_id"}, schema["required"]
    for call, want in zip(rec.calls, expected):
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        V.assert_documented("rest", "POST", PATH, call["body"])

    # what the spec says about the fields the recipe leans on
    said = " ".join(props["name"]["description"].split())
    assert "lowercase letters, numbers, and hyphens" in said, said
    assert props["user"]["default"] == "*", props["user"]
    assert "accepts any username" in " ".join(props["user"]["description"].split())
    assert props["encryption"]["enum"] == ["required", "optional", "forbidden"], props["encryption"]
    assert props["codecs"]["default"] == ["PCMU", "PCMA"], props["codecs"]
    assert props["ip_auth_enabled"]["default"] is False
    response = deref(list(op["responses"]["201"]["content"].values())[0]["schema"])
    assert "uri" in response["properties"], sorted(response["properties"])
    assert "Full SIP URI" in deref(response["properties"]["uri"])["description"]

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, AGENT_ID, NAME, URI)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["refused"] == 4, node
        assert [(c["method"], c["path"]) for c in node["captured"]] == [("POST", PATH)] * 2
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        assert node["dial"] == URI, node
        ts_note = "typescript sends the same two bodies and refuses the same names"

    print(f"ok: POST {PATH} with the spec's two required fields and encryption required, "
          f"once with the default user and once with reception; the response uri is "
          f"the dial string; the name rule, the * default, the codec defaults and the "
          f"encryption enum are read from the spec; four bad names are refused before "
          f"any request; {ts_note}")


if __name__ == "__main__":
    main()
