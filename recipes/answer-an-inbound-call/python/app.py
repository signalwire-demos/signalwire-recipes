"""Answer an inbound call.

SignalWire fetches a SWML document when the number rings and runs its verbs in
order: answer the call, say something, hang up.

`SWMLService` builds the same document the YAML surface holds, with one
advantage: the greeting comes from the environment and every verb is validated
against the SWML schema before it is served.

Written against signalwire-sdk 3.0.1 and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

GREETING = os.getenv(
    "GREETING",
    "Thanks for calling Ridgeline Cycles. We are open until six.",
)
MAX_DURATION = int(os.getenv("MAX_DURATION", "300"))

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="greeting", route="/greeting")
    service.reset_document()
    # until this runs the call is still ringing
    service.add_verb("answer", {"max_duration": MAX_DURATION})
    # "say:" speaks the text; a URL would play a file
    service.add_verb("play", {"url": f"say:{GREETING}"})
    # without this the call sits open until max_duration expires
    service.add_verb("hangup", {})
    return service


@app.route("/greeting", methods=["GET", "POST"])
def greeting():
    return jsonify(build().get_document())


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
