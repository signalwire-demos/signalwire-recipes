"""Prove the claim without a network.

Claim: a cXML `Record` with `transcribe` on makes the platform POST the
transcription to your URL, and one compat message sends the words and the
recording link to the owner. The payload does not carry the caller, so the
caller's number is put in the callback URL.

Proof: the voice route answers with cXML whose `Record` carries `transcribe`,
`transcribeCallback` pointing at this app with the caller in the query, and the
recording bounds. The transcription route is driven with the documented payload
signed over that exact URL: a `completed` one texts the owner the words and the
link, a repeat texts nothing, a `failed` one texts the link and says so, and an
unsigned post is refused with 403 and sends nothing. A send whose response never
arrives keeps its claim, so the same transcription texts nothing afterwards. The
compat spec's payload
requires the six fields used here and its status enum is completed or failed.
The TypeScript surface renders the same document and sends the same messages.
"""
import hashlib
import hmac
import json
import os
import pathlib
import sys
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import quote

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

KEY = "signing-key-test"
PUBLIC_URL = "https://recipes.example.test"
OWNER, SMS_FROM = "+15550100001", "+15550001111"
SEEN = pathlib.Path(tempfile.mkdtemp()) / "seen"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com", "SIGNALWIRE_SIGNING_KEY": KEY,
    "PUBLIC_URL": PUBLIC_URL, "OWNER_NUMBER": OWNER, "SMS_FROM": SMS_FROM,
    "SEEN_DIR": str(SEEN),
})

import verifylib as V  # noqa: E402

MESSAGES = "/api/laml/2010-04-01/Accounts/proj-1234/Messages"
CALLER = "+14155550123"
CALLBACK = f"{PUBLIC_URL}/transcription?from={quote(CALLER, safe='')}"
TEXT = "Hi, it is Dana. My bike is making a clicking noise. Call me back."
REC = "https://example.signalwire.com/recordings/RE123.wav"
GREETING = "No one is free right now. Leave a message after the beep."

EVENTS = [
    {"TranscriptionSid": "TR1", "TranscriptionText": TEXT,
     "TranscriptionStatus": "completed", "TranscriptionUrl": f"{PUBLIC_URL}/t/TR1",
     "RecordingSid": "RE123", "RecordingUrl": REC},
    {"TranscriptionSid": "TR1", "TranscriptionText": TEXT,
     "TranscriptionStatus": "completed", "TranscriptionUrl": f"{PUBLIC_URL}/t/TR1",
     "RecordingSid": "RE123", "RecordingUrl": REC},
    {"TranscriptionSid": "TR2", "TranscriptionText": "",
     "TranscriptionStatus": "failed", "TranscriptionUrl": f"{PUBLIC_URL}/t/TR2",
     "RecordingSid": "RE124", "RecordingUrl": REC},
]
ANSWERS = [{"texted": True, "sid": "SM1"},
           {"texted": False, "reason": "already texted"},
           {"texted": True, "sid": "SM2"}]
BODIES = [f"Voicemail from {CALLER}: {TEXT}\n{REC}",
          f"Voicemail from {CALLER}, not transcribed.\n{REC}"]


def sign(raw):
    return hmac.new(KEY.encode(), CALLBACK.encode() + raw, hashlib.sha1).hexdigest()


def check_document(xml, label):
    root = ET.fromstring(xml)
    assert root.tag == "Response", (label, root.tag)
    assert [c.tag for c in root] == ["Say", "Record"], (label, [c.tag for c in root])
    say, record = root
    assert say.text == GREETING, (label, say.text)
    assert record.get("transcribe") == "true", (label, record.attrib)
    assert record.get("transcribeCallback") == CALLBACK, (label, record.attrib)
    assert record.get("maxLength") == "120", (label, record.attrib)
    assert record.get("playBeep") == "true" and record.get("finishOnKey") == "#", \
        (label, record.attrib)
    assert record.get("timeout") == "5", (label, record.attrib)


def check_messages(calls, label):
    assert len(calls) == 2, (label, calls)
    for call, body in zip(calls, BODIES):
        assert (call["method"], call["path"]) == ("POST", MESSAGES), (label, call)
        assert call["body"] == {"To": OWNER, "From": SMS_FROM, "Body": body}, \
            (label, call["body"])
        V.assert_documented("compat", "POST", MESSAGES, call["body"])


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"sid": "SM1"}, {"sid": "SM2"}])
    V.record_everything(recipe.client, rec)
    web = recipe.app.test_client()

    # the document the caller's leg gets
    r = web.post("/voice", data={"From": CALLER, "To": "+15551230000"})
    assert r.status_code == 200 and r.mimetype == "text/xml", (r.status_code, r.mimetype)
    check_document(r.get_data(as_text=True), "python")

    # the transcription callbacks, signed over the URL that carries the caller
    answers = []
    for event in EVENTS:
        raw = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in event.items()).encode()
        res = web.post(f"/transcription?from={quote(CALLER, safe='')}", data=raw,
                       content_type="application/x-www-form-urlencoded",
                       headers={"X-Signalwire-Signature": sign(raw)})
        assert res.status_code == 200, (res.status_code, res.data)
        answers.append(res.get_json())
    assert answers == ANSWERS, answers
    check_messages(rec.calls, "python")

    # nothing unsigned sends anything
    raw = b"TranscriptionSid=TR9&TranscriptionStatus=completed"
    refused = web.post(f"/transcription?from={quote(CALLER, safe='')}", data=raw,
                       content_type="application/x-www-form-urlencoded")
    assert refused.status_code == 403, refused.status_code
    assert len(rec.calls) == 2, rec.calls

    # a send whose response never arrives keeps the claim: at most one text
    boom = dict(EVENTS[0], TranscriptionSid="TR9")

    def never_answers(*args, **kwargs):
        raise RuntimeError("the response never arrived")

    saved, rec.post = rec.post, never_answers
    raised = None
    try:
        recipe.handle(CALLER, boom)
    except Exception as exc:            # any failure leaves the outcome unknown
        raised = exc
    assert raised is not None, "the send should have raised"
    rec.post = saved
    again = recipe.handle(CALLER, boom)
    assert again == {"texted": False, "reason": "already texted"}, again
    assert len(rec.calls) == 2, rec.calls

    # the compat spec's payload, and what the Record verb turns on
    spec = V.spec("compat")
    hook = spec["webhooks"]["subpackage_recordingTranscriptions.transcription_status_callback"]
    op = hook["post"]
    sch = list(op["requestBody"]["content"].values())[0]["schema"]
    schemas = spec["components"]["schemas"]
    while "$ref" in sch:
        sch = schemas[sch["$ref"].split("/")[-1]]
    assert set(sch["required"]) == {"TranscriptionSid", "TranscriptionText",
                                    "TranscriptionStatus", "TranscriptionUrl",
                                    "RecordingSid", "RecordingUrl"}, sch["required"]
    # the caller is not in the payload, which is why it rides in the URL
    assert not {"From", "To", "Caller"} & set(sch["properties"]), sorted(sch["properties"])
    status = sch["properties"]["TranscriptionStatus"]
    while "$ref" in status:
        status = schemas[status["$ref"].split("/")[-1]]
    assert status["enum"] == ["completed", "failed"], status["enum"]
    description = op.get("description", "")
    assert "transcribe=true" in description, description[:200]
    assert "best-effort" in description, description[:200]

    node = V.node_surface(HERE, CALLER, json.dumps(EVENTS),
                          env={"SIGNALWIRE_SIGNING_KEY": KEY, "PUBLIC_URL": PUBLIC_URL,
                               "OWNER_NUMBER": OWNER, "SMS_FROM": SMS_FROM})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        check_document(node["document"], "typescript")
        assert node["answers"] == ANSWERS, node["answers"]
        check_messages(node["captured"], "typescript")
        assert node["unsigned"] == 403, node["unsigned"]
        # node:http does not await its listener, so a failed send that escaped
        # would end the process rather than answer. It is a 500, and the next
        # request is served and finds the claim.
        assert node["failed"] == 500, node["failed"]
        assert node["alive"] == 200, node["alive"]
        assert node["afterFailure"] == {"texted": False,
                                        "reason": "already texted"}, node
        ts_note = ("typescript renders the same document, sends the same two "
                   "messages, and answers a failed send with a 500 that keeps "
                   "the claim and the server")

    print(f"ok: the voice route answers with Record transcribe=true whose "
          f"transcribeCallback carries the caller; a completed transcription texts "
          f"{OWNER} the words and the recording, a repeat texts nothing, a failed one "
          f"texts the link and says so, and an unsigned callback is 403 with no message; "
          f"the payload has no caller field, which is why the URL carries it; {ts_note}")


if __name__ == "__main__":
    main()
