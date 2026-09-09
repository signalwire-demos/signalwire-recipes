"""Prove the claim without a network.

Claim: you create a conference room over REST with the fields the spec
requires, and a SWML `join_room` naming that room is the verb that puts the
leg running the document into it.

Proof: with the HTTP layer replaced by a recorder, `create_room` makes one
POST to the documented conference rooms path. Its body equals one expected
object, carries the spec's required fields, `name` and `enable_room_previews`,
and only documented ones.
Both SWML surfaces validate and contain answer, play, join_room, hangup in
order. Both carry the same room name in `join_room.name`, the verb's one
required field per the bundled schema. Expected values live here, not in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "ROOM_NAME": "workshop-standup",
})

import verifylib as V  # noqa: E402

ROOMS = "/api/fabric/resources/conference_rooms"
ROOM = "workshop-standup"


def check(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "play", "join_room", "hangup"], (label, V.verb_names(doc))
    assert V.first(doc, "join_room") == {"name": ROOM}, (label, V.first(doc, "join_room"))


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.fabric.conference_rooms._http = rec
    recipe.create_room()
    assert len(rec.calls) == 1, rec.calls
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", ROOMS), call
    body = call["body"]
    spec = V.spec("rest")
    schema = spec["paths"][ROOMS]["post"]["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert set(schema["required"]) == {"name", "enable_room_previews"}, schema["required"]
    assert set(schema["required"]) <= set(body), body
    assert set(body) <= set(schema["properties"]), sorted(set(body) - set(schema["properties"]))
    # the whole body, as one expected object
    assert body == {"name": ROOM, "display_name": "Workshop stand-up",
                    "enable_room_previews": False, "max_members": 10}, body
    V.assert_documented("rest", "POST", ROOMS, body)

    py = recipe.build().get_document()
    check(py, "python")
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    check(y, "yaml")
    assert py == y, "python and yaml surfaces differ"

    # the verb's one required field, per the bundled schema
    jr = V.swml_schema()["$defs"]["JoinRoom"]["properties"]["join_room"]
    assert jr["required"] == ["name"], jr

    print(f"ok: POST {ROOMS} with name={ROOM} and the spec's required fields; both "
          f"surfaces run answer, play, join_room({ROOM}), hangup; join_room requires name")


if __name__ == "__main__":
    main()
