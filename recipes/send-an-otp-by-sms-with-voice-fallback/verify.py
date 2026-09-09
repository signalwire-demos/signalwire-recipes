"""Prove the claim without a network.

Claim: the MFA API sends a code by SMS, re-sends it by voice call if asked, and
verifies it; you store no codes.

Proof: with the HTTP layer recorded, the three Flask routes make exactly the
documented MFA requests (POST /mfa/sms, POST /mfa/call, POST /mfa/{id}/verify)
with documented, required-complete bodies; the application code contains no
generated code, only the request id.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "SIGNALWIRE_PHONE_NUMBER": "+15550001111"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"id": "mfa-1", "success": True, "to": "+15552223333"},
        {"id": "mfa-2", "success": True, "to": "+15552223333"},
        {"success": False},
        {"success": True},
    ]))
    c = recipe.app.test_client()
    assert c.post("/otp/start", json={"to": "+15552223333"}).get_json() == {"request_id": "mfa-1"}
    assert c.post("/otp/voice", json={"to": "+15552223333"}).get_json() == {"request_id": "mfa-2"}
    assert c.post("/otp/verify", json={"request_id": "mfa-2", "token": "000000"}).get_json() == {"verified": False}
    assert c.post("/otp/verify", json={"request_id": "mfa-2", "token": "482913"}).get_json() == {"verified": True}

    sms, call, bad, good = rec.calls
    assert (sms["method"], sms["path"]) == ("POST", "/api/relay/rest/mfa/sms"), sms
    assert (call["method"], call["path"]) == ("POST", "/api/relay/rest/mfa/call"), call
    for r in (sms, call):
        V.assert_documented("rest", "POST", r["path"], body=r["body"])
        assert r["body"]["to"] == "+15552223333" and r["body"]["from"] == "+15550001111", r["body"]
        assert r["body"]["token_length"] == 6 and r["body"]["max_attempts"] == 3, r["body"]
    assert sms["body"] == call["body"], "voice fallback must carry the same parameters"
    for r in (bad, good):
        assert (r["method"], r["path"]) == ("POST", "/api/relay/rest/mfa/mfa-2/verify"), r
        V.assert_documented("rest", "POST", r["path"], body=r["body"])
    assert bad["body"] == {"token": "000000"} and good["body"] == {"token": "482913"}

    src = (HERE / "python" / "app.py").read_text(encoding="utf-8")
    assert "random" not in src and "secrets" not in src, "the app must not generate codes itself"
    print("ok: POST mfa/sms -> POST mfa/call (same params) -> POST mfa/{id}/verify(token); no code generated locally")
    return 0


if __name__ == "__main__":
    sys.exit(main())
