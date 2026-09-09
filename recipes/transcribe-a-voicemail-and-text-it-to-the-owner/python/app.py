"""Transcribe a voicemail and text it to the owner.

`<Record transcribe="true" transcribeCallback="...">` makes the platform
transcribe the recording and POST the words to your URL. That payload carries
the transcription and the recording, but not the caller, so the caller's number
rides in the callback URL the document is built with. The handler texts the
owner the words and the link.

Written against signalwire-sdk 3.0.1 (RestClient.compat) and Flask.

    python app.py            # serves POST /voice and POST /transcription
"""
import hashlib
import hmac
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape, quoteattr

from dotenv import load_dotenv
from flask import Flask, Response, abort, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# where this app is reachable; the callback URL is built from it
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com").rstrip("/")
# the person who gets the voicemail, and the messaging number it comes from
OWNER = os.getenv("OWNER_NUMBER", "+15550100001")
SMS_FROM = os.getenv("SMS_FROM", "+15550001111")
# the project's signing key, from the Dashboard
SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
if not SIGNING_KEY:
    raise SystemExit("SIGNALWIRE_SIGNING_KEY is required; see .env.example")
# one marker file per transcription already texted; swap for a unique key in
# your table
SEEN_DIR = Path(os.getenv("SEEN_DIR", "voicemails-seen"))

GREETING = "No one is free right now. Leave a message after the beep."
MAX_SECONDS = 120

DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}
HEX = re.compile(r"[0-9a-fA-F]+")


def signed(headers, url, raw_body, key=None):
    """True only when a signature header is present and matches; SHA-256 wins."""
    key = key or SIGNING_KEY
    for header, digest in DIGESTS.items():
        if header in headers:
            sent = headers[header]
            if not HEX.fullmatch(sent):
                return False
            want = hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()
            return hmac.compare_digest(sent, want)
    return False


def claim(transcription_sid):
    """Reserve this transcription, atomically. False when already taken.

    Check then act would let two concurrent callbacks both find the id unseen
    and both text the owner. "x" is O_EXCL, so only one can win.
    """
    SEEN_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", transcription_sid or "none")
    try:
        (SEEN_DIR / safe).open("x").close()
        return True
    except FileExistsError:
        return False


def callback_url(caller):
    """The transcription payload has no caller, so it travels in the URL."""
    return f"{PUBLIC_URL}/transcription?from={quote(caller or 'unknown', safe='')}"


def voicemail_document(caller):
    """cXML: greet, then record with transcription turned on."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f"  <Say>{escape(GREETING)}</Say>\n"
            f'  <Record transcribe="true" '
            f"transcribeCallback={quoteattr(callback_url(caller))} "
            f'maxLength="{MAX_SECONDS}" playBeep="true" finishOnKey="#" timeout="5"/>\n'
            "</Response>\n")


def notify(caller, payload):
    """One text to the owner. `completed` carries the words; `failed` does not."""
    if payload.get("TranscriptionStatus") == "completed":
        body = (f"Voicemail from {caller}: {payload.get('TranscriptionText', '')}\n"
                f"{payload.get('RecordingUrl', '')}")
    else:
        body = (f"Voicemail from {caller}, not transcribed.\n"
                f"{payload.get('RecordingUrl', '')}")
    return client.compat.messages.create(To=OWNER, From=SMS_FROM, Body=body)


def handle(caller, payload):
    """Text the owner once per transcription.

    The claim comes before the send and is not released on failure: a request
    that reached SignalWire and lost its response looks like one that never
    arrived, so at most one text per transcription is the safer failure.
    """
    if not claim(payload.get("TranscriptionSid")):
        return {"texted": False, "reason": "already texted"}
    message = notify(caller, payload)
    return {"texted": True, "sid": message.get("sid")}


app = Flask(__name__)


@app.post("/voice")
def voice():
    # the inbound voice webhook has historically been form-encoded
    inbound = request.form.to_dict() or request.get_json(silent=True) or {}
    document = voicemail_document(inbound.get("From"))
    return Response(document, mimetype="text/xml")


@app.post("/transcription")
def transcription():
    # the signature covers the URL SignalWire posted to, query string included
    url = f"{PUBLIC_URL}{urlsplit(request.url).path}"
    if request.query_string:
        url += "?" + request.query_string.decode()
    if not signed(request.headers, url, request.get_data()):
        abort(403)
    payload = request.form.to_dict() or request.get_json(silent=True) or {}
    return handle(request.args.get("from", "unknown"), payload)


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
