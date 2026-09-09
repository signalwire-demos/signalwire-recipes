"""Prove the claim without a network.

Claim: a fax is sent from a document URL and its status webhook reports pages
and result.

Proof: with the HTTP layer recorded, send() makes one documented POST to the
Compatibility Faxes endpoint with the required To/From/MediaUrl and a
StatusCallback; the status webhook records only final statuses with page count
or error code.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "PUBLIC_URL": "https://recipes.example.test",
                   "SIGNALWIRE_FAX_NUMBER": "+15550001111"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[{"sid": "FX1", "status": "queued"}]))
    assert recipe.send("+15552223333", "https://files.example.test/invoice.pdf") == "FX1"
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", "/api/laml/2010-04-01/Accounts/proj-1234/Faxes"), call
    V.assert_documented("compat", "POST", call["path"], body=call["body"])
    assert call["body"]["MediaUrl"].endswith(".pdf") and call["body"]["To"] == "+15552223333"
    assert call["body"]["StatusCallback"] == "https://recipes.example.test/fax-status"

    c = recipe.app.test_client()
    c.post("/fax-status", data={"FaxSid": "FX1", "FaxStatus": "sending"})
    assert recipe.outcomes == {}
    c.post("/fax-status", data={"FaxSid": "FX1", "FaxStatus": "delivered", "NumPages": "3"})
    assert recipe.outcomes["FX1"] == {"status": "delivered", "pages": "3", "error": None}
    c.post("/fax-status", data={"FaxSid": "FX2", "FaxStatus": "failed", "ErrorCode": "11"})
    assert recipe.outcomes["FX2"]["status"] == "failed" and recipe.outcomes["FX2"]["error"] == "11"
    print("ok: POST .../Faxes {To, From, MediaUrl, Quality, StatusCallback}; final statuses recorded with pages/error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
