"""Build a conference call, and control who is in it.

`join_conference` puts a call in a room named by a string. Two calls naming the
same room are in the same conference, and there is nothing to create first.

The room's lifetime belongs to whoever you say it does. `start_on_enter` and
`end_on_exit` are per participant, so a host can hold the room open and a guest
cannot end it by hanging up.

Members are managed over the Compatibility REST API once the room exists: mute
somebody, remove them, or list who is present.

Written against signalwire-sdk 3.0.1 (SWMLService and RestClient.compat) and
Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

ROOM = os.getenv("CONFERENCE_NAME", "standup")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

app = Flask(__name__)
present = {}   # call_sid -> the room they are in


def build(service=None, host=False):
    """One document per role. The room is the same; the powers differ."""
    service = service or SWMLService(name="conference", route="/conference")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("join_conference", {
        "name": ROOM,
        # only the host opens the room and closes it
        "start_on_enter": bool(host),
        "end_on_exit": bool(host),
        "muted": False,
        "beep": "onEnter",
        "max_participants": 25,
        "record": "do-not-record",
        "status_callback": f"{PUBLIC_URL}/conference-status",
        # one value: the schema takes a single event, not a list
        "status_callback_event": "join",
    })
    service.add_verb("hangup", {})
    return service


@app.route("/conference", methods=["GET", "POST"])
def guest():
    return jsonify(build().get_document())


@app.route("/conference/host", methods=["GET", "POST"])
def host():
    return jsonify(build(host=True).get_document())


@app.post("/conference-status")
def status():
    """Track membership so the controls below have something to act on."""
    # status_callback_event takes a single value, so this document asks for
    # join and nothing else. Departures are not delivered here.
    event = request.form.to_dict() or (request.get_json(silent=True) or {})
    sid = event.get("CallSid") or event.get("call_sid")
    if sid:
        present[sid] = event.get("ConferenceSid") or ROOM
    return "", 204


def mute(conference_sid, call_sid, muted=True):
    """Silence a member without removing them."""
    return client.compat.conferences.update_participant(
        conference_sid, call_sid, Muted="true" if muted else "false")


def remove(conference_sid, call_sid):
    """Drop a member from the room. Their call ends; the room does not."""
    return client.compat.conferences.remove_participant(conference_sid, call_sid)


def who_is_in(conference_sid):
    """The room's membership, from the platform rather than from our cache."""
    return client.compat.conferences.list_participants(conference_sid)


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
