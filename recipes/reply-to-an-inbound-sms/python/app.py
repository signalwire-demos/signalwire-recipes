"""Reply to an inbound SMS.

SignalWire POSTs the inbound message to this URL and executes the messaging
SWML document it returns. `reply` answers the sender on the same number. The
branching happens in Python here; swml/agent.yaml does the same with an inline
switch and no server at all.

Written against the documented inbound-message webhook payload and messaging
SWML `reply` (docs: swml/reference/messaging/reply).
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)

REPLIES = {
    "hours": "We are open Monday to Friday, nine to five, Eastern time.",
    "help": "Text HOURS for opening hours, or STOP to unsubscribe.",
    "stop": "You have been unsubscribed and will receive no more messages.",
}
DEFAULT = "Thanks for your message. A person will reply shortly."

opted_out = set()
received_media = []


def reply_for(message):
    """Pick the reply body for an inbound message dict (the webhook's `message`)."""
    body = (message.get("body") or "").strip().lower()
    sender = message.get("from")
    for m in message.get("media") or []:
        # MMS attachments arrive as URLs; download them from here.
        received_media.append(
            {"from": sender, "url": m["url"], "content_type": m["content_type"]})
    if body == "stop":
        # SignalWire does not manage STOP for you (see handle-opt-outs-yourself).
        opted_out.add(sender)
    if message.get("media") and not body:
        return "Got your picture, thanks."
    return REPLIES.get(body, DEFAULT)


def swml_reply(text):
    return {"version": "1.0.0", "sections": {"main": [{"reply": {"body": text}}]}}


@app.route("/sms", methods=["POST"])
def inbound():
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message") or {}
    return jsonify(swml_reply(reply_for(message)))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
