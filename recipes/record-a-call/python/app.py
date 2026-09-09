"""Record a call.

Background recording starts before the bridge, so the recording covers both
legs of the conversation. When it finishes, SignalWire POSTs the recording URL
to status_url; the Flask route below receives it.

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

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="record", route="/record")
    service.reset_document()
    service.add_verb("answer", {})
    # Before connect: the bridged leg is inside the recording.
    service.add_verb("record_call", {
        "format": "wav",
        "stereo": True,          # caller on one channel, agent on the other
        "direction": "both",
        "status_url": f"{PUBLIC_URL}/recording-status",
    })
    service.add_verb("play", {"url": "say:This call is recorded for quality purposes."})
    service.add_verb("connect", {"to": AGENT})
    service.add_verb("hangup", {})
    return service


@app.route("/record", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


recordings = {}


@app.post("/recording-status")
def recording_status():
    """The recording URL arrives here, not in the SWML fetch."""
    p = request.get_json(silent=True) or request.form.to_dict()
    call_id = p.get("call_id")
    if p.get("state") == "finished" and p.get("url"):
        recordings[call_id] = {"url": p["url"], "duration": p.get("duration")}
    return "", 204


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
