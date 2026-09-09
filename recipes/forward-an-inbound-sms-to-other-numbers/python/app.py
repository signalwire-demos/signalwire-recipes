"""Forward an inbound SMS to other numbers.

A text arriving on your number goes on to a list of recipients, prefixed with
the sender, and the sender gets no reply. `reply` is the Messaging SWML method
that sends a message; its `to` defaults to the sender, so naming `to` is what
turns a reply into a forward. The reference's own example is headed "Forward an
inbound message to another number".

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.

    python app.py            # serves POST /inbound
"""
import json
import os
import re

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request

# the SDK does not read .env for you
load_dotenv()

# who gets the copies, comma separated, E.164
RECIPIENTS = [n.strip() for n in os.getenv("FORWARD_TO", "+15550100001,+15550100002")
              .split(",") if n.strip()]

# SignalWire fetches the document with the credentials in the URL you give it,
# so the route wants them too
AUTH_USER = os.getenv("SWML_BASIC_AUTH_USER")
AUTH_PASSWORD = os.getenv("SWML_BASIC_AUTH_PASSWORD")
if not (AUTH_USER and AUTH_PASSWORD):
    raise SystemExit("SWML_BASIC_AUTH_USER and SWML_BASIC_AUTH_PASSWORD are required; "
                     "see .env.example")

# the carrier keywords; see handle-opt-outs-yourself for what to do with them
STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
# the platform's maximum SMS body, which the sender prefix eats into
MAX_BODY = 1600


def digits(number):
    return re.sub(r"\D", "", number or "")


def keyword(body):
    """The bare word a phone sent, with the punctuation people add."""
    return (body or "").strip().strip(".!? ").lower()


def targets(sender, received_on, recipients=None):
    """Everyone on the list once, except the sender and the receiving line.

    Leaving the receiving line in would text the number that just fired this
    webhook, which fires it again and forwards a second copy to everyone.
    """
    skip = {digits(sender), digits(received_on)}
    out = []
    for r in (RECIPIENTS if recipients is None else recipients):
        if digits(r) not in skip:
            skip.add(digits(r))          # a repeated entry is still one copy
            out.append(r)
    return out


def forwarded_body(sender, body):
    """The sender, then their words, inside the platform's body limit."""
    prefix = f"{sender}: "
    return prefix + (body or "")[:MAX_BODY - len(prefix)]


def forward_document(sender, received_on, body, recipients=None):
    """One reply per recipient, from the number that received the text."""
    steps = []
    if keyword(body) not in STOP_WORDS:
        for recipient in targets(sender, received_on, recipients):
            # `to` is what makes this a forward rather than a reply
            steps.append({"reply": {"to": recipient, "from": received_on,
                                    "body": forwarded_body(sender, body)}})
    # an opt-out is for you, not for the team; an empty document sends nothing
    return {"version": "1.0.0", "sections": {"main": steps}}


app = Flask(__name__)


@app.before_request
def gate():
    auth = request.authorization
    if not (auth and auth.username == AUTH_USER and auth.password == AUTH_PASSWORD):
        abort(Response(status=401, headers={"WWW-Authenticate": 'Basic realm="forward"'}))


@app.post("/inbound")
def inbound():
    payload = request.get_json(force=True, silent=True) or {}
    m = payload.get("message") or {}
    # the webhook's schema requires both; without them there is nothing to do
    if not (m.get("from") and m.get("to")):
        return jsonify({"error": "message.from and message.to are required"}), 400
    return jsonify(forward_document(m["from"], m["to"], m.get("body")))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
