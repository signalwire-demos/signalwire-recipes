"""Transcribe a call in the background.

Two REST commands and one webhook. The vendored REST spec's `calling.transcribe`
variant takes `control_id`, required, and a `status_url`.
`calling.transcribe.stop` takes the same `control_id`. When the transcription
is ready SignalWire may POST the transcribe status callback to `status_url`;
the spec calls it best-effort. Its `event_type` is
`calling.transcript.completed` or `calling.transcript.failed`, and
`params.text` is "The transcribed text of the call. Omitted when there is no
transcribed text."

Nothing here plays into the call or waits on it; the transcript is a document
that may arrive later. The status route accepts a callback only with
SignalWire's signature over it. The read route wants a bearer token of yours,
because a transcript is call content.

Written against signalwire-sdk 3.0.1 (RestClient.calling) and Flask.
"""
import hashlib
import hmac
import os

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

STATUS_URL = os.getenv("TRANSCRIBE_STATUS_URL")
SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
READ_TOKEN = os.getenv("READ_TOKEN")
REQUIRED = (("TRANSCRIBE_STATUS_URL", STATUS_URL),
            ("SIGNALWIRE_SIGNING_KEY", SIGNING_KEY),
            ("READ_TOKEN", READ_TOKEN))
for name, value in REQUIRED:
    if not value:
        raise SystemExit(f"{name} is required; see .env.example")

# the platform signs its webhooks: hex(HMAC(signing_key, url + raw_body)), SHA-256
# on call requests, SHA-1 on every signed request (docs/swml/guides/webhook-security)
DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}

CONTROL_ID = "call-transcript"

# call_id -> what arrived; swap for your database
TRANSCRIPTS = {}


def start(call_id):
    """Begin transcribing a live call. The callback, if it comes, goes to STATUS_URL."""
    return client.calling.transcribe(call_id, control_id=CONTROL_ID,
                                     status_url=STATUS_URL)


def stop(call_id):
    """Stop the transcription with this control id."""
    return client.calling.transcribe_stop(call_id, control_id=CONTROL_ID)


def signed(headers, url, raw_body):
    """True only when a signature header is present and matches, so a forged
    callback cannot overwrite a transcript."""
    key = SIGNING_KEY
    for header, digest in DIGESTS.items():
        if header in headers:
            sent = headers[header]
            if not all(c in "0123456789abcdefABCDEF" for c in sent):
                return False
            expected = hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()
            return hmac.compare_digest(sent, expected)
    return False


def record(event):
    """One status callback. `text` is absent when nothing was transcribed."""
    params = event["params"]
    TRANSCRIPTS[params["call_id"]] = {
        "status": event["event_type"].rsplit(".", 1)[-1],   # completed | failed
        "text": params.get("text"),
        "at": event["timestamp"],
    }


app = Flask(__name__)


@app.post("/transcripts")
def status():
    # SignalWire signs the URL it was given. A configured URL that already
    # carries a query is that URL; one without takes the request's query.
    url = STATUS_URL
    if "?" not in STATUS_URL and request.query_string:
        url += "?" + request.query_string.decode()
    if not signed(request.headers, url, request.get_data()):
        abort(403)
    record(request.get_json(force=True))
    return "", 204


@app.get("/transcripts/<call_id>")
def read(call_id):
    # transcripts are call content; a bearer token of yours gates the read
    if request.headers.get("Authorization") != f"Bearer {READ_TOKEN}":
        abort(401)
    return jsonify(TRANSCRIPTS.get(call_id) or {"status": "pending", "text": None})


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] in ("start", "stop"):
        print((start if sys.argv[1] == "start" else stop)(sys.argv[2]))
    elif len(sys.argv) == 1:
        app.run(port=int(os.getenv("PORT", "8080")))
    else:
        raise SystemExit("usage: python app.py            (serve the status URL)\n"
                         "       python app.py start|stop <call_id>")
