"""Relay calls and texts through a proxy number.

Two people share one number of yours and never learn each other's. Your
handler pairs them: a session says that on proxy P, participant A talks to B
and B talks to A. A call from A to P becomes `connect` to B with `from` set to
P, so B's phone shows the proxy; a text from A to P becomes a `reply` to B
from P. The schema calls `connect.from` "the caller ID to use when dialing the
number"; `reply` is the Messaging method, whose `to` defaults to the sender.

The inbound call and inbound message webhooks both carry `from` and `to`, which
is all the lookup needs. Sessions live in a file here, keyed by proxy and
participant, because the pairing and the two webhooks are different requests.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.

    python app.py            # serves POST /call, POST /message, POST /pair
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

# the number both parties see. Buy it first; buy-a-number-and-point-it-at-your-app
PROXY = os.getenv("PROXY_NUMBER", "+15550001111")

# where the pairings live; swap for your database
SESSIONS_PATH = Path(os.getenv("SESSIONS_PATH", "proxy-sessions.json"))

# /pair creates sessions and so decides who can reach whom; it wants a key the
# server holds and your own systems present as X-Proxy-Key
ADMIN_KEY = os.getenv("PROXY_ADMIN_KEY")

# both webhooks serve documents to whoever asks; SignalWire fetches them with
# the credentials in the URLs you give it, so the routes want them too
AUTH_USER = os.getenv("SWML_BASIC_AUTH_USER")
AUTH_PASSWORD = os.getenv("SWML_BASIC_AUTH_PASSWORD")
if not (AUTH_USER and AUTH_PASSWORD):
    raise SystemExit("SWML_BASIC_AUTH_USER and SWML_BASIC_AUTH_PASSWORD are required; "
                     "see .env.example")

NOT_ACTIVE = "This number is not active for your call."


def digits(number):
    return re.sub(r"\D", "", number or "")


def _key(proxy, participant):
    return f"{digits(proxy)}|{digits(participant)}"


def _load():
    if not SESSIONS_PATH.exists():
        return {}
    return json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))


def _save(sessions):
    tmp = SESSIONS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    os.replace(tmp, SESSIONS_PATH)


def pair(a, b, proxy=PROXY):
    """On this proxy, A reaches B and B reaches A. Returns the two keys written."""
    sessions = _load()
    # a participant is in one pairing at a time: drop the old partner's
    # route back, or the old partner could still reach them
    for participant in (a, b):
        old = sessions.pop(_key(proxy, participant), None)
        back = sessions.get(_key(proxy, old), "") if old else ""
        if old and _key(proxy, back) == _key(proxy, participant):
            del sessions[_key(proxy, old)]
    sessions[_key(proxy, a)] = b
    sessions[_key(proxy, b)] = a
    _save(sessions)
    return [_key(proxy, a), _key(proxy, b)]


def other_party(proxy, participant):
    """Who this participant reaches on this proxy, or None."""
    return _load().get(_key(proxy, participant))


def _render(service):
    # 3.0.1 renders the document as a JSON string
    return json.loads(service.render_document())


def call_document(caller, proxy):
    """A call to the proxy becomes a call to the other party, from the proxy."""
    service = SWMLService(name="proxy-call", route="/call")
    other = other_party(proxy, caller)
    if other:
        service.add_verb("connect", {"to": other, "from": proxy})
    else:
        service.add_verb("answer", {})
        service.add_verb("play", {"url": f"say:{NOT_ACTIVE}"})
        service.add_verb("hangup", {})
    return _render(service)


def message_document(sender, proxy, body):
    """A text to the proxy becomes a text to the other party, from the proxy.

    `reply` is the Messaging SWML method, and its `to` defaults to the sender,
    so naming `to` is what relays the text. SWMLService validates against the
    bundled Calling schema, which has no messaging methods, so the document is
    built as a dict, the way reply-to-an-inbound-sms builds its own.
    """
    other = other_party(proxy, sender)
    steps = []
    if other:
        steps.append({"reply": {"to": other, "from": proxy, "body": body or ""}})
    # an unknown sender gets an empty document: nothing sent, nothing kept
    return {"version": "1.0.0", "sections": {"main": steps}}


app = Flask(__name__)


@app.before_request
def gate():
    if request.path in ("/call", "/message"):
        auth = request.authorization
        if not (auth and auth.username == AUTH_USER and auth.password == AUTH_PASSWORD):
            challenge = {"WWW-Authenticate": 'Basic realm="proxy"'}
            abort(Response(status=401, headers=challenge))
    if request.path == "/pair":
        if not ADMIN_KEY or request.headers.get("X-Proxy-Key") != ADMIN_KEY:
            abort(403)


@app.post("/call")
def call():
    c = request.get_json(force=True).get("call") or {}
    return jsonify(call_document(c.get("from"), c.get("to") or PROXY))


@app.post("/message")
def message():
    m = request.get_json(force=True).get("message") or {}
    return jsonify(message_document(m.get("from"), m.get("to") or PROXY, m.get("body")))


@app.post("/pair")
def pair_route():
    body = request.get_json(force=True)
    return jsonify({"keys": pair(body["a"], body["b"], body.get("proxy", PROXY))})


if __name__ == "__main__":
    if not ADMIN_KEY:
        raise SystemExit("PROXY_ADMIN_KEY is required; see .env.example")
    app.run(port=int(os.getenv("PORT", "8080")))
