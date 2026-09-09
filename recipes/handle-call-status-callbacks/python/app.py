"""Handle call status callbacks.

Ask for the stages you want and SignalWire posts them to your URL as they
happen, best effort.
The vendored compat spec documents `StatusCallbackEvent` with "Valid values:
initiated, ringing, answered, completed, ringing_forwarded, ringing_queued.
Defaults to `completed`". This recipe asks for the first four. The spec also
documents the payload it posts: `CallSid`, `CallStatus`, `SequenceNumber`
("The order in which events occur, starting at 0"), `Timestamp`, `Direction`,
`From` and `To`. `CallDuration` is "Only present on the `completed` event".

The handler keys payloads by `CallSid` and orders them by `SequenceNumber`,
because the spec says events "may not appear" in order. `timeline()` rebuilds
the call from what arrived.

Written against signalwire-sdk 3.0.1 (RestClient.compat.calls) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

FROM = os.getenv("CALL_FROM")
CALL_URL = os.getenv("CALL_URL")
STATUS_URL = os.getenv("STATUS_CALLBACK_URL")
for name, value in (("CALL_FROM", FROM), ("CALL_URL", CALL_URL),
                    ("STATUS_CALLBACK_URL", STATUS_URL)):
    if not value:
        raise SystemExit(f"{name} is required; see .env.example")

# four of the six documented events, not the default of completed alone
EVENTS = ["initiated", "ringing", "answered", "completed"]

# CallSid -> {SequenceNumber: payload}; swap for your database
CALLS = {}


def place(to):
    """An outbound call that asks for the four stages in EVENTS at STATUS_URL."""
    return client.compat.calls.create(To=to, From=FROM, Url=CALL_URL,
                                      StatusCallback=STATUS_URL,
                                      StatusCallbackEvent=EVENTS,
                                      StatusCallbackMethod="POST")


def record(payload):
    """Store one callback under its call, keyed by sequence so order of arrival
    does not matter."""
    CALLS.setdefault(payload["CallSid"], {})[int(payload["SequenceNumber"])] = payload


def timeline(call_sid):
    """The call's life, rebuilt from whatever callbacks arrived."""
    events = CALLS.get(call_sid, {})
    ordered = [events[n] for n in sorted(events)]
    last = ordered[-1] if ordered else {}
    return {
        "call_sid": call_sid,
        "direction": last.get("Direction"),
        "from": last.get("From"),
        "to": last.get("To"),
        "steps": [{"seq": int(e["SequenceNumber"]), "status": e["CallStatus"],
                   "at": e["Timestamp"]} for e in ordered],
        "final": last.get("CallStatus"),
        "duration": int(last["CallDuration"]) if "CallDuration" in last else None,
    }


app = Flask(__name__)


@app.post("/status")
def status():
    # the spec documents the payload as JSON; a form-encoded post carries the
    # same field names, so the handler accepts both
    record(request.get_json(silent=True) or request.form.to_dict())
    return "", 204


@app.get("/calls/<call_sid>")
def life(call_sid):
    """The timeline. The process that holds the store serves it."""
    return jsonify(timeline(call_sid))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(place(sys.argv[1]))
    else:
        app.run(port=int(os.getenv("PORT", "8080")))
