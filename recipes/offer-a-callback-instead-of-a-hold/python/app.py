"""Offer a callback instead of a hold.

A caller who has waited long enough is let go with a promise, and the return
call opens already knowing what they said.

The shape is forced by one constraint: a leg already waiting in a queue cannot
be redirected into new SWML. So the release is designed rather than the
redirect. `wait_time` caps the wait, the document falls through when the cap is
reached, and everything after `enter_queue` is the release path.

The context travels on the outbound call, in the document handed to `dial`.
The caller is not asked anything twice.

Written against signalwire-sdk 3.0.1 (SWMLService and RestClient.calling) and
Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire.rest import RestClient
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

QUEUE = os.getenv("QUEUE_NAME", "support")
FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

# How long anyone waits before being offered the way out, in seconds.
MAX_WAIT = int(os.getenv("MAX_WAIT_SECONDS", "180"))

app = Flask(__name__)

# What each caller said, recorded by the intake. Knowing why somebody called
# is not the same as owing them a call back.
context = {}

# Who is actually owed a callback. Only a caller whose wait ran out lands
# here, which is what stops a served caller being rung about a solved problem.
owed = {}


def build(service=None):
    """Queue the caller, and describe what happens when the wait runs out."""
    service = service or SWMLService(name="queue", route="/queue")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("enter_queue", {
        "queue_name": QUEUE,
        # a string, not a boolean: the field takes a URL or inline SWML, and
        # "false" is how you say "carry on in this document instead"
        "transfer_after_bridge": "false",
        # the cap: without it the document never reaches the release path
        "wait_time": MAX_WAIT,
        "wait_url": f"{PUBLIC_URL}/hold-music",
        "status_url": f"{PUBLIC_URL}/queue-status",
    })
    # Everything below runs only if the wait ran out. A caller who reached an
    # agent never gets here.
    service.add_verb("play", {"url": (
        "say:Nobody is free yet. We will call you back on this number as soon "
        "as someone is, and you will not have to explain it again.")})
    service.add_verb("hangup", {})
    return service


@app.route("/queue", methods=["GET", "POST"])
def queue():
    return jsonify(build().get_document())


def remember(number, reason):
    """Record why somebody called, before they are handed to the queue.

    This owes them nothing yet. A caller who reaches an agent is remembered
    and never called back.
    """
    if not number:
        return False
    context[number] = {"reason": reason or ""}
    return True


def owe_callback(number):
    """Promise a call back, once the wait has actually run out.

    Deliberately an explicit call rather than something read off the queue's
    status callback: nothing documents that payload, and a recipe that guesses
    at one proves its own invention. Whatever watches the queue calls this.
    """
    if not number:
        # a promise you cannot ring is not a promise
        return False
    owed[number] = context.get(number, {})
    return True


@app.route("/hold-music", methods=["GET", "POST"])
def hold_music():
    """What wait_url points at. A URL with nothing behind it is silence."""
    return jsonify({
        "version": "1.0.0",
        "sections": {"main": [
            {"play": {"url": os.getenv("HOLD_AUDIO", "silence:30"),
                      "auto_answer": False}},
        ]},
    })


@app.post("/queue-status")
def queue_status():
    """Queue events, logged. The promise is not made from this payload."""
    app.logger.info("queue status: %s", request.get_data(as_text=True)[:200])
    return "", 204


def return_document(context):
    """What the caller hears when we ring back, built from what they said."""
    reason = context.get("reason") or "your call earlier"
    return {
        "version": "1.0.0",
        "sections": {
            "main": [
                {"answer": {}},
                {"play": {"url": (
                    f"say:This is the callback you asked for, about {reason}. "
                    f"Connecting you now.")}},
                {"connect": {"to": f"queue:{QUEUE}"}},
                {"hangup": {}},
            ]
        },
    }


def call_back(number):
    """Ring the promise. The context goes with the call, not into a lookup."""
    if number not in owed:
        # nothing was promised, so nothing is rung. Dialling here would call
        # somebody who already spoke to an agent.
        return None
    promised = owed[number]
    result = client.calling.dial(**{
        "from": FROM,
        "to": number,
        "swml": return_document(promised),
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["answered", "ended"],
    })
    # Discharged only once the request went out. Popping first would lose the
    # promise on a failed dial, and the caller would never hear from us.
    owed.pop(number, None)
    return result


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
