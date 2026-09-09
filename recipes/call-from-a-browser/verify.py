"""Prove the claim without a network.

Claim: a page dials a phone number or Resource address over WebRTC with a token
your server minted.

Proof: with the HTTP layer recorded, the /token route makes one documented POST
to /api/fabric/subscribers/tokens with the required `reference`, returns only
the minted token (never the project API token), and the TypeScript client
connects with that token and dials the destination via the documented v4
client calls.
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
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "DIAL_DESTINATION": "/public/support"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[{"token": "eyJ.sat", "refresh_token": "rt"}]))
    c = recipe.app.test_client()
    out = c.post("/token", json={"user": "dana@example.test", "display_name": "Dana"}).get_json()
    assert out == {"token": "eyJ.sat", "destination": "/public/support"}, out
    (t,) = rec.calls
    assert (t["method"], t["path"]) == ("POST", "/api/fabric/subscribers/tokens"), t
    V.assert_documented("rest", "POST", t["path"], body=t["body"])
    assert t["body"]["reference"] == "dana@example.test"
    assert "PT-test" not in str(out)

    ts = (HERE / "typescript" / "index.ts").read_text(encoding="utf-8")
    for needle in ("new SignalWire(", "StaticCredentialProvider", "client.connect()", "client.dial(",
                   "audio: true", "video: false", "hangup()"):
        assert needle in ts, f"typescript client lacks {needle}"
    assert re.search(r"fetch\([^)]*['\"]/token['\"]", ts), "client must fetch its token from the server"
    compiled = V.type_check_typescript(HERE, "@signalwire/js")
    print(f"ok: POST subscribers/tokens(reference) -> browser dials /public/support with audio; {compiled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
