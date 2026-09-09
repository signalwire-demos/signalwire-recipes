"""Call when a text goes undelivered.

A message status callback that reports `undelivered` or `failed` carries the
recipient and the body, so one `POST /api/calling/calls` with inline SWML
places a call that speaks the same message. The callback is checked against
SignalWire's signature before it spends anything, and each message id is
claimed with an atomic marker before the call is placed, so two deliveries of
one callback cannot place two calls.

Written against signalwire-sdk 3.0.1 (RestClient.calling) and Flask.

    python app.py            # serves POST /message-status
"""
import hashlib
import hmac
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# a voice-capable number you own; the call comes from it
FROM = os.getenv("VOICE_FROM", "+15550001111")
# the status_callback URL you gave when sending. The signature is over the URL
# SignalWire posted to, so the configured query is stripped here and the
# request's own is appended below; otherwise a tagged URL would be signed twice.
STATUS_URL = os.getenv("STATUS_URL", "https://your-host.example.com/message-status")
_PARTS = urlsplit(STATUS_URL)
STATUS_PATH = _PARTS.path
STATUS_BASE = urlunsplit((_PARTS.scheme, _PARTS.netloc, _PARTS.path, "", ""))
# the project's signing key, from the Dashboard
SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
if not SIGNING_KEY:
    raise SystemExit("SIGNALWIRE_SIGNING_KEY is required; see .env.example")
# one marker file per message id already called; swap for a unique key in your table
HANDLED_DIR = Path(os.getenv("HANDLED_DIR", "handled-messages"))

# the two statuses that mean the text will not arrive
FALLBACK_ON = {"undelivered", "failed"}

DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}
HEX = re.compile(r"[0-9a-fA-F]+")


def signed_url(query_string=""):
    """The URL the signature is over: the configured one, with this query."""
    return STATUS_BASE + (("?" + query_string) if query_string else "")


def signed(headers, url, raw_body, key=None):
    """True only when a signature header is present and matches; SHA-256 wins."""
    key = key or SIGNING_KEY
    if not key:
        return False                    # an empty key would verify anything
    for header, digest in DIGESTS.items():
        if header in headers:
            sent = headers[header]
            if not HEX.fullmatch(sent):
                return False
            want = hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()
            return hmac.compare_digest(sent.lower(), want)
    return False


def claim(message_id):
    """Reserve this message id, atomically. False when it was already taken."""
    HANDLED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # "x" is O_EXCL: two processes cannot both win this
        (HANDLED_DIR / re.sub(r"[^A-Za-z0-9_-]", "_", message_id)).open("x").close()
        return True
    except FileExistsError:
        return False


def spoken(body):
    """One line. A newline in the body would fail the play url's own pattern."""
    return "We could not reach you by text. The message was: " + " ".join(body.split())


def call_document(body):
    """Answer, speak the text, hang up: the whole call, inline in the request."""
    return {"version": "1.0.0", "sections": {"main": [
        {"answer": {}},
        {"play": {"url": f"say:{spoken(body)}"}},
        {"hangup": {}}]}}


def place_call(to, body):
    """One request; `from` is a Python keyword, so the params go in a dict."""
    return client.calling.dial(**{"from": FROM, "to": to, "swml": call_document(body),
                                  "timeout": 25})


def handle(event):
    """Fall back only for a final failure, and only once per message."""
    status = event.get("status")
    if status not in FALLBACK_ON:
        return {"called": False, "reason": str(status or "none")}
    # the spec requires both; without them there is nothing to call or to key on
    message_id, to = event.get("id"), event.get("to")
    if not message_id:
        return {"called": False, "reason": "no message id"}
    if not to:
        return {"called": False, "reason": "no recipient"}
    if not claim(message_id):
        return {"called": False, "reason": "already handled"}
    # The claim stays whatever happens next. A request that reached SignalWire
    # and lost its response looks exactly like one that never arrived, so
    # releasing here would let a redelivery place a second billed call. At most
    # one call per message is the safer failure, and the marker is where a
    # reconciler looks; see Limitations.
    call = place_call(to, event.get("body") or "")
    return {"called": True, "call_id": str(call.get("id") or "")}


app = Flask(__name__)


@app.before_request
def gate():
    # the signature is bound to the URL SignalWire posted to
    if request.path != STATUS_PATH:
        abort(403)
    url = signed_url(request.query_string.decode())
    if not signed(request.headers, url, request.get_data()):
        abort(403)


@app.post(STATUS_PATH)
def message_status():
    return jsonify(handle(request.get_json(force=True, silent=True) or {}))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
