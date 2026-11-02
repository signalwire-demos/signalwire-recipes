"""Manage video rooms over REST.

A video room is a Fabric Conference Room resource, and one REST family creates,
lists, reads, updates and deletes it: /api/fabric/resources/conference_rooms.
A room per meeting is a create with a member cap and a join window. A meeting
that is over is a delete. The SDK wraps the calls as
client.fabric.conference_rooms.

Written against signalwire-sdk 3.0.1 (RestClient.fabric) and the vendored REST
spec, tools/openapi/rest.json.

    python app.py create standup-0900 --members 12 --opens 2026-11-03T08:50:00Z
    python app.py list
    python app.py show <room_id>
    python app.py update <room_id> --members 20
    python app.py delete <room_id>
"""
import argparse
import json
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

# The spec's bounds: max_members is 0 to 300, remove_after_seconds_elapsed is
# 0 to 200000. Outside them the platform answers 422, so the helpers refuse
# the value before any request is made.
MAX_MEMBERS = 300
MAX_REMOVE_AFTER = 200_000


def _bounded(key, value, top):
    value = int(value)
    if not 0 <= value <= top:
        raise ValueError(f"{key} must be between 0 and {top}, not {value}")
    return value


def create_room(name, max_members=None, join_from=None, join_until=None,
                remove_at=None, remove_after_seconds_elapsed=None, **options):
    """A room per meeting.

    `max_members` caps the room. `join_from` and `join_until` bound when joining
    works, `remove_at` empties the room at a time, and
    `remove_after_seconds_elapsed` removes each participant that long after
    they joined. Times are ISO 8601 with a zone. `enable_room_previews` is the
    one other field the create requires.
    """
    body = {"name": name,
            "display_name": options.pop("display_name", name),
            "enable_room_previews": options.pop("enable_room_previews", False)}
    body.update(options)
    if max_members is not None:
        body["max_members"] = _bounded("max_members", max_members, MAX_MEMBERS)
    for key, value in (("join_from", join_from), ("join_until", join_until),
                       ("remove_at", remove_at)):
        if value:
            body[key] = value
    if remove_after_seconds_elapsed is not None:
        body["remove_after_seconds_elapsed"] = _bounded(
            "remove_after_seconds_elapsed", remove_after_seconds_elapsed,
            MAX_REMOVE_AFTER)
    return client.fabric.conference_rooms.create(**body)


def list_rooms():
    """Every conference room in the project."""
    return client.fabric.conference_rooms.list()


def get_room(room_id):
    return client.fabric.conference_rooms.get(room_id)


def addresses_of(room_id):
    """The addresses a room answers at; the browser dials one of these."""
    return client.fabric.conference_rooms.list_addresses(room_id)


def update_room(room_id, **changes):
    """The update is a PUT, and the spec requires `enable_room_previews` and
    `sync_audio_video` on every PUT. An update that changes neither has to
    carry them anyway, so read the room first and send its current values.
    The response schema lets `sync_audio_video` come back null; the request
    schema does not take null, so an unset flag is sent as False."""
    current = get_room(room_id)["conference_room"]
    body = {"enable_room_previews": current.get("enable_room_previews") is True,
            "sync_audio_video": current.get("sync_audio_video") is True}
    if "max_members" in changes:
        changes["max_members"] = _bounded("max_members", changes["max_members"],
                                          MAX_MEMBERS)
    body.update(changes)
    return client.fabric.conference_rooms.update(room_id, **body)


def delete_room(room_id):
    """A DELETE by id. The platform answers 204 with no body."""
    client.fabric.conference_rooms.delete(room_id)
    return {"deleted": room_id}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--members", type=int)
    c.add_argument("--opens", help="join_from, ISO 8601")
    c.add_argument("--closes", help="join_until, ISO 8601")
    c.add_argument("--ends", help="remove_at, ISO 8601")
    sub.add_parser("list")
    sub.add_parser("show").add_argument("room_id")
    u = sub.add_parser("update")
    u.add_argument("room_id")
    u.add_argument("--members", type=int)
    u.add_argument("--display-name")
    sub.add_parser("delete").add_argument("room_id")
    a = p.parse_args(argv)

    if a.cmd == "create":
        out = create_room(a.name, max_members=a.members, join_from=a.opens,
                          join_until=a.closes, remove_at=a.ends)
    elif a.cmd == "list":
        out = list_rooms()
    elif a.cmd == "show":
        out = {"room": get_room(a.room_id), "addresses": addresses_of(a.room_id)}
    elif a.cmd == "update":
        changes = {}
        if a.members is not None:
            changes["max_members"] = a.members
        if a.display_name:
            changes["display_name"] = a.display_name
        out = update_room(a.room_id, **changes)
    else:
        out = delete_room(a.room_id)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
