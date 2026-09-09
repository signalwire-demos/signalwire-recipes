"""Translate a call in real time.

`live_translate` opens a translation session on the call. Each side speaks its
own language and hears the other rendered by a TTS voice you pick per
direction. The verb starts before `connect`, so the leg the bridge adds is
inside the session.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
AGENT = os.getenv("AGENT_NUMBER", "+15550100001")
FROM_LANG = os.getenv("FROM_LANG", "en-US")
TO_LANG = os.getenv("TO_LANG", "es-ES")
FROM_VOICE = os.getenv("FROM_VOICE", "Polly.Joanna")
TO_VOICE = os.getenv("TO_VOICE", "Polly.Lucia")

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="translate", route="/translate")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("live_translate", {"action": {"start": {
        "from_lang": FROM_LANG,
        "to_lang": TO_LANG,
        # the voice each side hears the other in
        "from_voice": FROM_VOICE,
        "to_voice": TO_VOICE,
        # both legs: without local-caller the agent is never translated
        "direction": ["remote-caller", "local-caller"],
        # translation events are POSTed here while the call runs
        "webhook": f"{PUBLIC_URL}/translation",
        "live_events": True,
        "ai_summary": True,
        "speech_engine": "deepgram",
    }}})
    service.add_verb("connect", {"to": AGENT})
    service.add_verb("hangup", {})
    return service


@app.route("/translate", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
