"""Prove the claim without a network.

Claim: a TwiML app moves to SignalWire by changing the REST base and the
credentials. The compat client posts the same Calls body to the LaML path on
your Space, and your cXML handler serves the same document it served before.

Proof: the HTTP layer is a recorder. `place` makes one POST to
`/api/laml/2010-04-01/Accounts/<project id>/Calls`, the path the SDK's compat
namespace builds from the project id. The body is exactly `To`, `From` and
`Url`: the compat spec's two required fields and the handler URL. The Flask
handler answers a POST with `text/xml` that parses. Its root is `Response` and
its children are `Say`, with the greeting and a voice, and `Hangup`. The project
id and token appear nowhere in that document. Expected values live here, not in
app.py.
"""
import os
import pathlib
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "CALL_FROM": "+15550001111",
    "VOICE_URL": "https://app.example.com/voice",
})

import verifylib as V  # noqa: E402

CALLS = "/api/laml/2010-04-01/Accounts/proj-1234/Calls"
TO = "+15550002222"
GREETING = "Thanks for calling Ridgeline Cycles. The workshop opens at nine."


def main():
    V.sdk_banner()
    import app as recipe

    # the REST side: the same Calls request, on the LaML path of your Space
    rec = V.Recorder(responses=[{"sid": "CA-verifier", "status": "queued"}])
    recipe.client.compat.calls._http = rec
    recipe.place(TO)
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", CALLS), call
    assert call["body"] == {"To": TO, "From": "+15550001111",
                            "Url": "https://app.example.com/voice"}, call["body"]
    V.assert_documented("compat", "POST", call["path"], call["body"])
    spec = V.spec("compat")
    schema = spec["paths"]["/Accounts/{AccountSid}/Calls"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert set(schema["required"]) == {"To", "From"}, schema["required"]
    assert "Url" in schema["properties"], sorted(schema["properties"])

    # the handler side: the TwiML document, unchanged
    r = recipe.app.test_client().post("/voice")
    assert r.status_code == 200 and r.mimetype == "text/xml", (r.status_code, r.mimetype)
    body = r.get_data(as_text=True)
    root = ET.fromstring(body)
    assert root.tag == "Response", root.tag
    assert [child.tag for child in root] == ["Say", "Hangup"], [c.tag for c in root]
    say = root.find("Say")
    assert say.text == GREETING and say.get("voice") == "Polly.Salli", (say.text, say.attrib)
    assert "proj-1234" not in body and "PT-test" not in body

    print(f"ok: POST {CALLS} with To, From and Url, the compat spec's shape; /voice answers "
          f"text/xml with Response > Say({GREETING[:22]}...) + Hangup")


if __name__ == "__main__":
    main()
