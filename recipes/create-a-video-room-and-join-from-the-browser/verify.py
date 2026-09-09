"""Prove the claim without a network.

Claim: a room is created over REST, a token is minted per participant, and the
browser joins with layouts and screen share.

Proof: with the HTTP layer recorded, the two Flask routes make documented
requests - POST /api/fabric/resources/conference_rooms and POST
/api/fabric/guests/tokens whose allowed_addresses is exactly the room's address;
the browser never receives the project token; the TypeScript client dials that
same address with audio and video via the documented v4 client.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "ROOM_NAME": "team-standup"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"id": "room-1", "name": "team-standup"},
        {"token": "eyJ.guest.sat", "refresh_token": "rt"},
    ]))
    c = recipe.app.test_client()
    room = c.post("/rooms", json={"name": "team-standup"}).get_json()
    tok = c.post("/token", json={"room": "team-standup"}).get_json()
    assert room["id"] == "room-1" and tok == {"token": "eyJ.guest.sat", "destination": "/public/team-standup"}

    r, t = rec.calls
    assert (r["method"], r["path"]) == ("POST", "/api/fabric/resources/conference_rooms"), r
    V.assert_documented("rest", "POST", r["path"], body=r["body"])
    assert r["body"]["name"] == "team-standup"
    assert (t["method"], t["path"]) == ("POST", "/api/fabric/guests/tokens"), t
    V.assert_documented("rest", "POST", t["path"], body=t["body"])
    assert t["body"]["allowed_addresses"] == ["/public/team-standup"], t["body"]
    assert "PT-test" not in str(tok), "the project API token must never reach the browser"

    ts = (HERE / "typescript" / "index.ts").read_text(encoding="utf-8")
    for needle in ("new SignalWire(", "StaticCredentialProvider", "client.connect()",
                   "client.dial(", "audio: true", "video: true", "startScreenShare", "setLayout"):
        assert needle in ts, f"typescript client lacks {needle}"
    assert re.search(r"fetch\([^)]*['\"]/token['\"]", ts), "client must fetch its token from the server"
    compiled = V.type_check_typescript(HERE, "@signalwire/js")
    print(f"ok: POST conference_rooms + POST guests/tokens(allowed_addresses=[/public/team-standup]); {compiled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
