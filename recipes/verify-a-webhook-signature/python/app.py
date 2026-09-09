"""Verify a webhook signature.

SignalWire signs the requests it makes to your webhooks. The SWML webhook
security guide (https://signalwire.com/docs/swml/guides/webhook-security)
documents two headers: `X-Signalwire-Signature`, "HMAC-SHA1, hex encoded",
on every signed request, and `X-Signalwire-SHA256-Signature`, "HMAC-SHA256,
hex encoded", on call requests. The signed payload is "the request URL
concatenated directly with the raw request body, with no separator", so
`signature = hex(HMAC(signing_key, url + raw_body))`. The key is in the
Dashboard under API Credentials, as Signing Key.

The URL is the one SignalWire has for your webhook, query string included, so
it comes from configuration rather than from the request. A proxy or a tunnel
rewrites what the request thinks its URL is; the platform signed the one you
gave it.

Written against Flask and the standard library. There is no SDK here.
"""
import hashlib
import hmac
import os
import re
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request

# load .env into the environment; there is no SDK here to do it
load_dotenv()

SIGNING_KEY = os.getenv("SIGNALWIRE_SIGNING_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
REQUIRED = (("SIGNALWIRE_SIGNING_KEY", SIGNING_KEY), ("WEBHOOK_URL", WEBHOOK_URL))
for name, value in REQUIRED:
    if not value:
        raise SystemExit(f"{name} is required; see .env.example")
# WEBHOOK_URL is the URL without a query string: the gate appends each request's
# own query before checking, so a configured query would be signed twice
if "?" in WEBHOOK_URL:
    raise SystemExit("WEBHOOK_URL must not carry a query string; "
                     "the request's own is appended")
WEBHOOK_PATH = urlsplit(WEBHOOK_URL).path

DIGESTS = {"X-Signalwire-SHA256-Signature": hashlib.sha256,
           "X-Signalwire-Signature": hashlib.sha1}
HEX = re.compile(r"[0-9a-fA-F]+")


def expected(key, url, raw_body, digest):
    """hex(HMAC(key, url + raw_body)), the documented formula."""
    return hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()


def verify(headers, url, raw_body, key=None):
    """True only when a signature header is present and matches.

    The SHA-256 header wins when both are sent. A request with neither header
    is not signed, so it is not SignalWire's."""
    key = key or SIGNING_KEY
    for header, digest in DIGESTS.items():
        if header in headers:
            # presence selects the digest, so an empty or wrong SHA-256 header
            # is a failed SHA-256 check, not a fallback to SHA-1
            sent = headers[header]
            if not HEX.fullmatch(sent):
                return False        # not a hex digest at all; compare_digest wants ASCII
            return hmac.compare_digest(sent, expected(key, url, raw_body, digest))
    return False


app = Flask(__name__)


@app.before_request
def gate():
    """Runs before any route. The route handler does not run for a bad signature."""
    # a signature is bound to the URL SignalWire posted to, so a valid one
    # replayed at another path on this host is refused before it is checked
    if request.path != WEBHOOK_PATH:
        abort(403)
    url = WEBHOOK_URL
    if request.query_string:
        url += "?" + request.query_string.decode()
    if not verify(request.headers, url, request.get_data()):
        abort(403)


@app.post("/webhook")
def webhook():
    return jsonify({"version": "1.0.0", "sections": {"main": [
        {"answer": {}},
        {"play": {"url": "say:Thanks for calling Ridgeline Cycles."}},
        {"hangup": {}}]}})


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
