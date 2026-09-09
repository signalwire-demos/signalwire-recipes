"""Prove the claim without a network.

Claim: one POST creates a themed video conference from a `display_name` and
options the spec documents. One GET lists the tokens the spec documents for
it, each with a name, a token and scopes.

Proof: the HTTP layer is a recorder that answers the create with an `id` and
the token list with one token. `launch` makes one POST to the documented
conferences path. Its body equals one expected object, whose keys are all
documented and include `display_name`, the spec's one required field, and the
spec's 200 schema carries `id`. `tokens` makes one GET to the documented
conference tokens path for that id and returns the recorder's whole page,
links and data. The spec's token schema carries `name`, `token` and `scopes`. A second launch with overrides and no name or
join-window arguments sends exactly the overridden defaults and neither of
those keys.
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

CONFERENCES = "/api/video/conferences"
CID = "4a1f0a5e-6f2b-4c3d-9e8f-0b1c2d3e4f5a"
TOKENS = f"{CONFERENCES}/{CID}/conference_tokens"
# the whole documented page: links and data
TOKEN_PAGE = {"links": {"self": f"https://example.signalwire.com{TOKENS}"},
              "data": [{"id": "t1", "name": "moderator", "token": "x",
                        "scopes": ["conference.moderator"]}]}


def deref(spec, node):
    while isinstance(node, dict) and "$ref" in node:
        node = spec["components"]["schemas"][node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"id": CID, "display_name": "Workshop stand-up"}, TOKEN_PAGE])
    recipe.client.video.conferences._http = rec

    conf = recipe.launch("Workshop stand-up", name="workshop-standup", record_on_start=True,
                         join_from="2026-09-03T09:00:00Z", join_until="2026-09-03T10:00:00Z")
    assert conf["id"] == CID
    listed = recipe.tokens(conf["id"])
    assert listed == TOKEN_PAGE, listed
    assert len(rec.calls) == 2, rec.calls
    create, toks = rec.calls

    spec = V.spec("rest")
    assert (create["method"], create["path"]) == ("POST", CONFERENCES), create
    body = create["body"]
    schema = deref(spec, spec["paths"][CONFERENCES]["post"]["requestBody"]["content"]["application/json"]["schema"])
    assert schema["required"] == ["display_name"], schema.get("required")
    # the whole body, as one expected object
    assert body == {"display_name": "Workshop stand-up", "name": "workshop-standup",
                    "record_on_start": True, "quality": "720p", "layout": "grid-responsive",
                    "light_primary": "#F72A72", "dark_primary": "#F72A72",
                    "join_from": "2026-09-03T09:00:00Z",
                    "join_until": "2026-09-03T10:00:00Z"}, body
    assert set(body) <= set(schema["properties"]), sorted(set(body) - set(schema["properties"]))
    created = spec["paths"][CONFERENCES]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in created:
        created = spec["components"]["schemas"][created["$ref"].split("/")[-1]]
    assert "id" in created["properties"], sorted(created["properties"])
    V.assert_documented("rest", "POST", CONFERENCES, body)

    assert (toks["method"], toks["path"]) == ("GET", TOKENS), toks
    assert toks["params"] is None, toks
    V.assert_documented("rest", "GET", TOKENS, None)
    resp = deref(spec, spec["paths"]["/api/video/conferences/{id}/conference_tokens"]["get"]
                 ["responses"]["200"]["content"]["application/json"]["schema"])
    token = deref(spec, resp["properties"]["data"]["items"])
    assert {"id", "name", "token", "scopes"} <= set(token["properties"]), sorted(token["properties"])

    # overrides reach the body, and the name and join-window keys stay out when not given
    rec2 = V.Recorder(responses=[{"id": "conf-2"}])
    recipe.client.video.conferences._http = rec2
    recipe.launch("Quick call", quality="1080p", layout="1x1", primary="#044EF4")
    (second,) = rec2.calls
    assert second["body"] == {"display_name": "Quick call", "record_on_start": False,
                              "quality": "1080p", "layout": "1x1",
                              "light_primary": "#044EF4", "dark_primary": "#044EF4"}, second["body"]

    print(f"ok: POST {CONFERENCES} with display_name and documented options, then GET "
          f"{TOKENS}; the spec's token carries name, token and scopes")


if __name__ == "__main__":
    main()
