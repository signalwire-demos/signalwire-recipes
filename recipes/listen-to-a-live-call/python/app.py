"""Listen to a live call.

`tap` forks the call's audio to a socket you own while the call continues. The
participants hear nothing: this is a copy of the media, not a third party in
the room.

It runs before `connect`, so the leg the bridge adds is inside the tap. After
`connect` it would not run until the bridge had already ended.

`direction` decides whose audio you get. `listen` is what the party hears,
`speak` is what they say, and `both` is the conversation.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
AUDIO_WS = os.getenv("AUDIO_WS", "wss://your-host.example.com/ws/audio")
AGENT = os.getenv("AGENT_NUMBER", "+15550100001")

app = Flask(__name__)
taps = {}   # control_id -> last status seen


def build(service=None):
    service = service or SWMLService(name="listen", route="/listen")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("tap", {
        # where the copy goes: ws://, wss:// or rtp://
        "uri": AUDIO_WS,
        # both sides, so the socket receives the conversation
        "direction": "both",
        # PCMU is the default and what most decoders expect
        "codec": "PCMU",
        # a handle for stop_tap
        "control_id": "supervisor-audio",
        "status_url": f"{PUBLIC_URL}/tap-status",
    })
    # before connect: a tap placed after it never runs while anyone is talking
    service.add_verb("connect", {"to": AGENT})
    service.add_verb("hangup", {})
    return service


@app.route("/listen", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


@app.post("/tap-status")
def tap_status():
    event = request.get_json(force=True, silent=True) or request.form.to_dict()
    control_id = event.get("control_id") or "unknown"
    taps[control_id] = event.get("state") or event.get("status") or "unknown"
    return "", 204


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
