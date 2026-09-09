"""Run an SMS survey over several messages.

A survey is one outbound text and then a conversation the platform does not
hold for you. Each reply arrives at your inbound webhook on its own, so the
state that says which question a number is on lives in a file here, keyed by
the sender. The webhook answers with a messaging SWML `reply` carrying the next
question, a re-ask for an answer that does not parse, or the closing line.

STOP ends everything for that number, and a number that has stopped is never
sent a first question. Only SignalWire may post to the webhook: the signature
is checked before any state changes.

Written against signalwire-sdk 3.0.1 (RestClient) and the documented inbound
message webhook and messaging SWML.

    python app.py                       # serve /inbound and /begin
    python app.py begin +14155550123    # text the first question
"""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()
# 3.0.1 has no messaging namespace; the send goes through the shared HttpClient
http = client._http

FROM = os.getenv("SMS_FROM")
SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
INBOUND_URL = os.getenv("INBOUND_URL")
# /begin sends billable texts with your credentials, so it is behind a key the
# server holds and your own systems present as X-Survey-Key
ADMIN_KEY = os.getenv("SURVEY_ADMIN_KEY")

# where each number's progress lives; swap for your database
STATE_PATH = Path(os.getenv("SURVEY_STATE_PATH", "survey-state.json"))

# the platform signs its webhooks: hex(HMAC(signing_key, url + raw_body)), SHA-256
# on call requests, SHA-1 on every signed request (docs/swml/guides/webhook-security)
DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}

# the questions, in order: a key for the answer, the text, and how to read a reply
QUESTIONS = [
    ("rating", "Thanks for visiting Ridgeline Cycles. How was your service today? "
               "Reply with a number from 1 to 5.", "scale"),
    ("recommend", "Would you recommend us to a friend? Reply YES or NO.", "yes_no"),
    ("comment", "Anything we should know? Reply with a sentence, or SKIP.", "text"),
]
DONE = "That is everything. Thank you. Reply STOP at any time to opt out."
REASK = {"scale": "Please reply with a single number from 1 to 5.",
         "yes_no": "Please reply YES or NO."}

# the single words that end the survey, compared whole after trim and lowercase
STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}
STOPPED = "You will receive no more messages from Ridgeline Cycles."


class OptedOut(Exception):
    """Raised before any request is made."""


def _load():
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save(state):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def keyword(body):
    return (body or "").strip().lower()


def parse(kind, body):
    """The answer a reply means, or None when it does not fit the question."""
    word = keyword(body)
    if kind == "scale":
        return int(word) if word in {"1", "2", "3", "4", "5"} else None
    if kind == "yes_no":
        return {"yes": True, "y": True, "no": False, "n": False}.get(word)
    return "" if word == "skip" else (body or "").strip() or None


def reply(text):
    """A messaging SWML document with one verb: the text back to the sender."""
    return {"version": "1.0.0", "sections": {"main": [{"reply": {"body": text}}]}}


def silence():
    return {"version": "1.0.0", "sections": {"main": []}}


def begin(to):
    """Text the first question. A number that said STOP is refused, not texted."""
    state = _load()
    record = state.get(to, {})
    if record.get("stopped"):
        raise OptedOut(f"{to} opted out; no message sent")
    state[to] = {"step": 0, "answers": {}, "stopped": False}
    _save(state)
    body = {"to": to, "from": FROM, "body": QUESTIONS[0][1]}
    return http.post("/api/messaging/messages", body=body)


def handle_inbound(message):
    """Advance one number's survey by one reply. Returns the SWML to run."""
    sender = message["from"]
    state = _load()
    record = state.get(sender)
    word = keyword(message.get("body"))

    if word in STOP_WORDS:
        state[sender] = {**(record or {"step": 0, "answers": {}}), "stopped": True}
        _save(state)
        return reply(STOPPED)
    if not record or record["stopped"]:
        # not in a survey, or out of it: nothing is sent and nothing is
        # recorded. This runs before the cache, or a late retry of an earlier
        # answer would text a question to a number that said STOP
        return silence()
    seen = record.get("seen", {})
    if message.get("message_id") in seen:
        # the webhook was delivered again, maybe late: the answer it got the
        # first time, and the state is not touched. A retried rating parsed at
        # the comment step would otherwise be stored as the comment
        return reply(seen[message["message_id"]])
    if record["step"] >= len(QUESTIONS):
        return silence()

    key, _, kind = QUESTIONS[record["step"]]
    answer = parse(kind, message.get("body"))
    if answer is None:
        return reply(REASK.get(kind, QUESTIONS[record["step"]][1]))

    record["answers"][key] = answer
    record["step"] += 1
    text = DONE if record["step"] == len(QUESTIONS) else QUESTIONS[record["step"]][1]
    record.setdefault("seen", {})[message["message_id"]] = text
    _save(state)
    return reply(text)


def signed(headers, url, raw_body, key=None):
    """True only when a signature header is present and matches."""
    key = key or SIGNING_KEY
    for header, digest in DIGESTS.items():
        sent = headers.get(header)
        if sent:
            expected = hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()
            return hmac.compare_digest(sent, expected)
    return False


app = Flask(__name__)


@app.before_request
def gate():
    """Only SignalWire may advance a survey."""
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


@app.post("/begin")
def begin_route():
    """Your systems start a survey here, never the public internet."""
    if not ADMIN_KEY or request.headers.get("X-Survey-Key") != ADMIN_KEY:
        abort(403)
    try:
        return jsonify(begin(request.get_json(force=True)["to"]))
    except OptedOut as exc:
        return jsonify({"error": str(exc)}), 409


if __name__ == "__main__":
    for name, value in (("SMS_FROM", FROM), ("SIGNALWIRE_SIGNING_KEY", SIGNING_KEY),
                        ("INBOUND_URL", INBOUND_URL), ("SURVEY_ADMIN_KEY", ADMIN_KEY)):
        if not value:
            raise SystemExit(f"{name} is required; see .env.example")
    if len(sys.argv) == 3 and sys.argv[1] == "begin":
        print(begin(sys.argv[2]))
    else:
        app.run(port=int(os.getenv("PORT", "8080")))
