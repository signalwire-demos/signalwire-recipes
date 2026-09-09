"""Start live transcription.

`live_transcribe` starts a transcription session on the call and POSTs events to
a webhook: partial results as they occur (live_events), final utterances per
leg, and an AI summary when the session ends (ai_summary). The Flask route below
receives them and keeps finals and the summary; partials are printed and
dropped.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
AGENT = os.getenv("AGENT_NUMBER", "+15550100001")
LANG = os.getenv("TRANSCRIBE_LANG", "en")

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="transcribe", route="/transcribe")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("live_transcribe", {"action": {"start": {
        "webhook": f"{PUBLIC_URL}/transcript",
        "lang": LANG,
        "live_events": True,       # partials as they occur
        "ai_summary": True,        # a summary when the session ends
        "direction": ["remote-caller", "local-caller"],
        "speech_engine": "deepgram",
    }}})
    service.add_verb("connect", {"to": AGENT})
    service.add_verb("hangup", {})
    return service


@app.route("/transcribe", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


transcripts = {}   # call_id -> [{"who", "text"}]
summaries = {}     # call_id -> text


def classify(event):
    """Return ('partial'|'final'|'summary'|'other', payload)."""
    if event.get("summary") or event.get("type") == "summary":
        return "summary", event
    if event.get("type") == "partial" or event.get("partial") is True:
        return "partial", event
    if event.get("text") or event.get("transcript"):
        return "final", event
    return "other", event


@app.post("/transcript")
def transcript():
    event = request.get_json(force=True, silent=True) or {}
    kind, e = classify(event)
    call_id = e.get("call_id", "unknown")
    if kind == "final":
        transcripts.setdefault(call_id, []).append(
            {"who": e.get("direction") or e.get("channel", "?"),
             "text": e.get("text") or e.get("transcript")})
    elif kind == "summary":
        summaries[call_id] = e.get("summary") or e.get("text")
    else:
        print("partial:", e.get("text") or e.get("transcript"))
    return "", 204


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
