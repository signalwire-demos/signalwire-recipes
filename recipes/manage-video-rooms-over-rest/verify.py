"""Prove the claim without a network.

Claim: a video room is a Fabric Conference Room resource, and one REST family
creates, lists, reads, updates and deletes it. A room per meeting is a create
with a member cap and a join window; a meeting that is over is a delete.

Proof: with the HTTP layer recorded, the helpers make exactly the documented
requests on /api/fabric/resources/conference_rooms, in order: POST, GET the
collection, GET one, GET its addresses on the singular conference_room path,
GET then PUT for the update, DELETE. The create body carries the spec's two
required fields plus the cap and the window, and every key sent is documented.
The PUT carries the two fields the spec requires on every update, read back
from the room. The bounds the helpers refuse at are the spec's own bounds, read
from the spec here and compared, and a cap above the maximum is refused before
any request. The TypeScript surface is held to the same sequence and bodies.
Expected values live here, not in the code under test.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com"})

import verifylib as V  # noqa: E402

BASE = "/api/fabric/resources/conference_rooms"
ADDRESSES = "/api/fabric/resources/conference_room/{id}/addresses"
ROOM_ID = "0b7a2f3e-9c41-4d6e-8a52-1f0e3d2c4b5a"
NAME = "standup-0900"
OPENS, CLOSES, ENDS = ("2026-11-03T08:50:00Z", "2026-11-03T09:30:00Z",
                       "2026-11-03T10:00:00Z")
CAP, NEW_CAP = 12, 20
PLAN = {"name": NAME, "max_members": CAP, "join_from": OPENS, "join_until": CLOSES,
        "remove_at": ENDS}
CREATE = {"name": NAME, "display_name": NAME, "enable_room_previews": False,
          "max_members": CAP, "join_from": OPENS, "join_until": CLOSES, "remove_at": ENDS}
# the room as the platform reads it back; previews on, so the PUT must say so
ROOM = {"id": ROOM_ID, "display_name": NAME, "type": "video_room",
        "conference_room": {"id": ROOM_ID, "name": NAME, "enable_room_previews": True,
                            "sync_audio_video": False, "max_members": CAP}}
UPDATE = {"enable_room_previews": True, "sync_audio_video": False, "max_members": NEW_CAP}
# the same room read back with sync_audio_video null, which the response
# schema allows and the update request schema does not; the PUT sends False
UNSET = {**ROOM, "conference_room": {**ROOM["conference_room"], "sync_audio_video": None}}
RENAME = {"enable_room_previews": True, "sync_audio_video": False, "display_name": "Stand-up"}
SEQUENCE = [("POST", BASE), ("GET", BASE), ("GET", f"{BASE}/{ROOM_ID}"),
            ("GET", ADDRESSES.replace("{id}", ROOM_ID)),
            ("GET", f"{BASE}/{ROOM_ID}"), ("PUT", f"{BASE}/{ROOM_ID}"),
            ("GET", f"{BASE}/{ROOM_ID}"), ("PUT", f"{BASE}/{ROOM_ID}"),
            ("DELETE", f"{BASE}/{ROOM_ID}")]


def body_schema(spec, path, method):
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    op = spec["paths"][path][method]
    return deref(list(op["requestBody"]["content"].values())[0]["schema"]), deref


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[
        ROOM, {"data": [ROOM]}, ROOM,
        {"data": [{"id": "addr-1", "name": NAME, "type": "room"}]},
        ROOM, {**ROOM, "conference_room": {**ROOM["conference_room"], "max_members": NEW_CAP}},
        UNSET, ROOM,
        {},
    ])
    V.record_everything(recipe.client, rec)

    made = recipe.create_room(**PLAN)
    assert made["id"] == ROOM_ID
    assert recipe.list_rooms()["data"][0]["id"] == ROOM_ID
    assert recipe.get_room(ROOM_ID)["conference_room"]["name"] == NAME
    assert recipe.addresses_of(ROOM_ID)["data"][0]["name"] == NAME
    recipe.update_room(ROOM_ID, max_members=NEW_CAP)
    recipe.update_room(ROOM_ID, display_name="Stand-up")
    assert recipe.delete_room(ROOM_ID) == {"deleted": ROOM_ID}

    sent = [(c["method"], c["path"]) for c in rec.calls]
    assert sent == SEQUENCE, sent

    spec = V.spec("rest")
    # the create: the spec's two required fields, the cap and the window, and
    # every key documented
    create = rec.calls[0]["body"]
    assert create == CREATE, create
    V.assert_documented("rest", "POST", BASE, create)
    schema, deref = body_schema(spec, BASE, "post")
    assert set(schema["required"]) == {"name", "enable_room_previews"}, schema["required"]
    for key in ("join_from", "join_until", "remove_at"):
        assert deref(schema["properties"][key])["format"] == "date-time", key

    # the bounds the helpers refuse at are the spec's bounds
    members = deref(schema["properties"]["max_members"])
    assert (members["minimum"], members["maximum"]) == (0, recipe.MAX_MEMBERS), members
    after = deref(schema["properties"]["remove_after_seconds_elapsed"])
    assert (after["minimum"], after["maximum"]) == (0, recipe.MAX_REMOVE_AFTER), after

    # the update: a PUT carrying the two fields the spec requires on every PUT,
    # read back from the room, plus the change
    put = rec.calls[5]["body"]
    assert put == UPDATE, put
    V.assert_documented("rest", "PUT", f"{BASE}/{{id}}", put)
    put_schema, deref = body_schema(spec, f"{BASE}/{{id}}", "put")
    assert set(put_schema["required"]) == {"enable_room_previews", "sync_audio_video"}
    assert set(put_schema["required"]) <= set(put), put
    # the response schema lets sync_audio_video be null and the request schema
    # does not, so a room read back with it unset is updated with False (codex)
    read_schema = deref(list(spec["paths"][f"{BASE}/{{id}}"]["get"]["responses"]["200"]
                             ["content"].values())[0]["schema"])
    read_room = deref(read_schema["properties"]["conference_room"])
    assert deref(read_room["properties"]["sync_audio_video"])["type"] == ["boolean", "null"]
    for key in ("enable_room_previews", "sync_audio_video"):
        assert deref(put_schema["properties"][key])["type"] == "boolean", key
    rename = rec.calls[7]["body"]
    assert rename == RENAME, rename
    V.assert_documented("rest", "PUT", f"{BASE}/{{id}}", rename)
    # the delete answers 204 and nothing else
    assert "204" in spec["paths"][f"{BASE}/{{id}}"]["delete"]["responses"]

    # a cap above the spec's maximum is refused before any request
    rec2 = V.record_everything(recipe.client, V.Recorder())
    try:
        recipe.create_room(NAME, max_members=recipe.MAX_MEMBERS + 1)
    except ValueError as exc:
        assert str(recipe.MAX_MEMBERS) in str(exc), exc
    else:
        raise AssertionError("created a room with a cap the spec refuses")
    assert rec2.calls == [], rec2.calls

    node = V.node_surface(HERE, json.dumps(PLAN), ROOM_ID, str(NEW_CAP))
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert [(c["method"], c["path"]) for c in node["captured"]] == SEQUENCE, node
        assert node["captured"][0]["body"] == CREATE, node["captured"][0]
        assert node["captured"][5]["body"] == UPDATE, node["captured"][5]
        assert node["captured"][7]["body"] == RENAME, node["captured"][7]
        assert node["deleted"] == {"deleted": ROOM_ID}, node
        assert node["refused"] is True and node["afterRefusal"] == 0, node
        assert (node["maxMembers"], node["maxRemoveAfter"]) == (
            recipe.MAX_MEMBERS, recipe.MAX_REMOVE_AFTER), node
        ts_note = ("typescript sends the same nine requests with the same create and "
                   "update bodies, sends False for flags read back as null, reads the "
                   "204, and refuses the same cap")

    print(f"ok: POST {BASE} with name, enable_room_previews, a cap of {CAP} and a "
          f"join window; GET the collection, one room and its addresses; GET then PUT "
          f"carrying the two required fields, twice, the second with sync_audio_video "
          f"read back as null and sent as False; DELETE; the refused bounds are the spec's "
          f"own; a cap above {recipe.MAX_MEMBERS} sends nothing; {ts_note}")


if __name__ == "__main__":
    main()
