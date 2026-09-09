"""Handle opt-outs yourself.

SignalWire does not manage STOP for you. The platform messaging page says
"Customers are responsible for handling inbound stop requests and removing
those customers from subscriber lists." It adds that messages should not go
out again "unless they have opted back in via an Unstop request"
(https://signalwire.com/docs/platform/messaging). So a handler of yours
receives the inbound message webhook and records the opt-out. Every later
send checks that record before it makes a request.

The inbound webhook is the SWML inbound message webhook: SignalWire POSTs a
JSON body whose `message` carries `from`, `to` and `body`, and expects a SWML
document back. A STOP gets a one-method document, `reply`, confirming the
opt-out; START or UNSTOP gets one confirming the return. Anything else gets an
empty document, which sends nothing. The handler accepts the webhook only with
SignalWire's signature over it, because a forged START would undo a real STOP.

Written against signalwire-sdk 3.0.1 (RestClient) and Flask.
"""
import hashlib
import hmac
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

# 3.0.1 wraps no method for POST /api/messaging/messages, so the send goes
# through the HTTP client every namespace shares
http = client._http

FROM = os.getenv("SMS_FROM")
SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
INBOUND_URL = os.getenv("INBOUND_URL")
for name, value in (("SMS_FROM", FROM), ("SIGNALWIRE_SIGNING_KEY", SIGNING_KEY),
                    ("INBOUND_URL", INBOUND_URL)):
    if not value:
        raise SystemExit(f"{name} is required; see .env.example")

# the platform signs its webhooks: hex(HMAC(signing_key, url + raw_body)), SHA-256
# on call requests, SHA-1 on every signed request (docs/swml/guides/webhook-security)
DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}

# the single words this handler honours, compared whole after trim and lowercase
STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
START_WORDS = {"start", "unstop"}
STOPPED = ("You are unsubscribed from Ridgeline Cycles messages. "
           "Reply START to opt back in.")
RESUMED = "You are opted back in to Ridgeline Cycles messages. Reply STOP at any time."

# number -> when it opted out; swap for your database
OPT_OUTS = {}


class OptedOut(Exception):
    """Raised before any request is made."""


def keyword(body):
    return (body or "").strip().lower()


def signed(headers, url, raw_body, key=None):
    """True only when a signature header is present and matches. A forged STOP
    or START would otherwise rewrite the record, so this runs first."""
    key = key or SIGNING_KEY
    for header, digest in DIGESTS.items():
        sent = headers.get(header)
        if sent:
            expected = hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()
            return hmac.compare_digest(sent, expected)
    return False


def reply(from_number, to_number, body):
    """A Messaging SWML document with one method: the confirmation text.

    `reply` defaults `to` to the sender and `from` to the number that received
    the message. Both are named here so the document says what it does.
    """
    answer = {"to": to_number, "from": from_number, "body": body}
    return {"version": "1.0.0", "sections": {"main": [{"reply": answer}]}}


def handle_inbound(message):
    """Record STOP or START and return the SWML document to run.

    `message` is the webhook's `message` object. Any other text returns an
    empty document, which sends nothing and records nothing."""
    word = keyword(message.get("body"))
    sender, ours = message["from"], message["to"]
    if word in STOP_WORDS:
        OPT_OUTS[sender] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return reply(ours, sender, STOPPED)
    if word in START_WORDS:
        OPT_OUTS.pop(sender, None)
        return reply(ours, sender, RESUMED)
    return {"version": "1.0.0", "sections": {"main": []}}


def send(to, body):
    """Every outbound send checks the record first. A refused send makes no request."""
    if to in OPT_OUTS:
        raise OptedOut(f"{to} opted out at {OPT_OUTS[to]}; no message sent")
    message = {"to": to, "from": FROM, "body": body}
    return http.post("/api/messaging/messages", body=message)


app = Flask(__name__)


@app.before_request
def gate():
    """Only SignalWire may report a STOP or a START."""
    if request.path == "/inbound":
        url = INBOUND_URL
        if request.query_string:
            url += "?" + request.query_string.decode()
        if not signed(request.headers, url, request.get_data()):
            abort(403)


@app.post("/inbound")
def inbound():
    payload = request.get_json(force=True)
    return jsonify(handle_inbound(payload["message"]))


@app.post("/send")
def outbound():
    """Your send path, in the process that holds the record. Put it behind
    your own authentication before anything else can reach it."""
    payload = request.get_json(force=True)
    try:
        sent = send(payload["to"], payload["body"])
    except OptedOut as e:
        return jsonify({"sent": False, "reason": str(e)}), 403
    return jsonify({"sent": True, "id": sent.get("id")}), 202


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
