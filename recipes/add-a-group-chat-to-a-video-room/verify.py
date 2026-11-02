"""Prove the claim without a network.

Claim: everyone in a video room shares one text thread that outlives the call,
and the browser reads and writes it through the room's address with a token
your server mints.

Proof: with the HTTP layer recorded, the /token route makes one documented POST
to /api/fabric/subscribers/tokens carrying `reference` and `display_name`,
answers with the minted token and the room's address and never with the
project API token, and refuses a request that names no user before any request
is made. The TypeScript page dials that address and uses the room's address for
text through the documented v4 members: `call.address$`, `textMessages$`,
`values$`, `hasMore$`, `loadMore()` and `sendText()`. It is type-checked
against the installed Browser SDK, which is where wrong member names are
caught. Expected values live here, not in the code under test.
"""
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "ROOM_NAME": "team-standup"})

import verifylib as V  # noqa: E402

TOKENS = "/api/fabric/subscribers/tokens"
USER, NAME = "dana@example.test", "Dana"
TOKEN = "eyJ.subscriber.sat"
DESTINATION = "/public/team-standup"
# every member of the v4 client the page depends on, in the order it uses them
MEMBERS = ("new SignalWire(", "StaticCredentialProvider", "client.connect()",
           "client.dial(", "audio: true", "video: true", "call.address$",
           ".textMessages$", ".values$", ".hasMore$", ".loadMore()", ".sendText(")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"token": TOKEN, "refresh_token": "rt"},
    ]))
    web = recipe.app.test_client()
    out = web.post("/token", json={"user": USER, "display_name": NAME,
                                   "room": "team-standup"}).get_json()
    assert out == {"token": TOKEN, "destination": DESTINATION}, out
    assert "PT-test" not in str(out), "the project API token must never reach the browser"

    (t,) = rec.calls
    assert (t["method"], t["path"]) == ("POST", TOKENS), t
    V.assert_documented("rest", "POST", TOKENS, body=t["body"])
    # a subscriber token, with the user it is for and the name others see
    assert t["body"] == {"reference": USER, "display_name": NAME}, t["body"]

    # the spec: `reference` is the one required field, and the chat guide's own
    # example uses one Subscriber Access Token per person
    spec = V.spec("rest")
    schema = spec["paths"][TOKENS]["post"]["requestBody"]["content"]["application/json"]["schema"]
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert schema["required"] == ["reference"], schema["required"]

    # no user, no token, no request
    rec2 = V.record_everything(recipe.client, V.Recorder())
    r = web.post("/token", json={"display_name": NAME})
    assert r.status_code == 400, r.status_code
    assert rec2.calls == [], rec2.calls

    ts = (HERE / "typescript" / "index.ts").read_text(encoding="utf-8")
    for needle in MEMBERS:
        assert needle in ts, f"typescript client lacks {needle}"
    assert re.search(r"fetch\([^)]*['\"]/token['\"]", ts), "client must fetch its token from the server"

    # the page the dev server serves: it loads the script and carries every
    # element the script looks up, and the dev server forwards /token to the
    # Flask app, or `npm start` is a 404 and the recipe does not run (codex)
    html = (HERE / "typescript" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<script type="module" src="/index\.ts">', html), "index.html must load index.ts"
    for element_id in re.findall(r"getElementById\(\"([a-z-]+)\"\)", ts):
        assert f'id="{element_id}"' in html, f"index.html lacks #{element_id}"
    vite = (HERE / "typescript" / "vite.config.ts").read_text(encoding="utf-8")
    assert re.search(r"proxy:\s*\{\s*\"/token\"", vite), "vite.config.ts must proxy /token"
    compiled = V.type_check_typescript(HERE, "@signalwire/js")

    print(f"ok: POST {TOKENS}(reference, display_name) -> the browser dials {DESTINATION} "
          f"and reads and writes the room's thread through call.address$; a request with "
          f"no user is a 400 and sends nothing; {compiled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
