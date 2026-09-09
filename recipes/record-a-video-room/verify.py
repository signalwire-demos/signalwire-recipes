"""Prove the claim without a network.

Claim: `record_on_start: true` on a room makes the platform record each of its
sessions. A session's recordings list over REST, each with a `uri`, a `status`
and a `duration`, and a DELETE by recording id asks for deletion and answers 204.

Proof: the HTTP layer is a recorder. The five helpers make five requests in
order. They POST the room with exactly `name`, `display_name` and
`record_on_start: true`, then GET the sessions, GET the session's recordings,
GET one recording, and DELETE it. Every path and body is documented. The spec
requires `name` on the room and describes `record_on_start` as starting a
recording when a session starts. Its recording schema carries `uri`, `status`,
`duration`, `format` and `room_session_id`, and the delete answers 204. Whether
the platform deletes the file is live behaviour; the request and the documented
answer are what is proven. Expected values live here, not in app.py.
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

ROOMS = "/api/video/rooms"
SESSIONS = "/api/video/room_sessions"
RECORDINGS = "/api/video/room_recordings"
SESSION = "5e9c1f2a-3b4d-4c5e-8f60-718293a4b5c6"
REC = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
URI = "https://example.signalwire.com/video/recordings/a1b2c3d4.mp4"


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def response(spec, path, method):
    op = spec["paths"][path][method]
    code = next(c for c in op["responses"] if c.startswith("2"))
    content = op["responses"][code].get("content", {})
    if not content:
        return code, {}
    schema = deref(spec, content["application/json"]["schema"])
    if "data" in schema.get("properties", {}):
        schema = deref(spec, deref(spec, schema["properties"]["data"]).get("items"))
    return code, schema.get("properties", {})


def main():
    V.sdk_banner()
    import app as recipe

    entry = {"id": REC, "room_session_id": SESSION, "status": "completed", "duration": 1812.4,
             "format": "mp4", "uri": URI, "size_in_bytes": 190_000_000}
    rec = V.Recorder(responses=[{"id": "room-1", "name": "workshop-standup", "record_on_start": True},
                                {"data": [{"id": SESSION, "room_id": "room-1"}], "links": {}},
                                {"data": [entry], "links": {}}, entry, {}])
    for ns in (recipe.client.video.rooms, recipe.client.video.room_sessions,
               recipe.client.video.room_recordings):
        ns._http = rec

    recipe.create_room()
    found = recipe.sessions()
    listed = recipe.recordings_of(found["data"][0]["id"])
    one = recipe.recording(listed["data"][0]["id"])
    recipe.delete_recording(one["id"])

    expected = [("POST", ROOMS), ("GET", SESSIONS), ("GET", f"{SESSIONS}/{SESSION}/recordings"),
                ("GET", f"{RECORDINGS}/{REC}"), ("DELETE", f"{RECORDINGS}/{REC}")]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    room, *rest_calls = rec.calls
    assert room["body"] == {"name": "workshop-standup", "display_name": "Workshop stand-up",
                            "record_on_start": True}, room
    for c in rest_calls:
        assert c["body"] is None and c["params"] is None, c

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", ROOMS, room["body"])
    V.assert_documented("rest", "GET", SESSIONS, None)
    V.assert_documented("rest", "GET", f"{SESSIONS}/{{id}}/recordings", None)
    V.assert_documented("rest", "GET", f"{RECORDINGS}/{{id}}", None)
    V.assert_documented("rest", "DELETE", f"{RECORDINGS}/{{id}}", None)

    # the spec's word on the switch
    create = deref(spec, spec["paths"][ROOMS]["post"]["requestBody"]["content"]["application/json"]["schema"])
    assert create["required"] == ["name"], create["required"]
    switch = deref(spec, create["properties"]["record_on_start"])
    assert switch["type"] == "boolean", switch
    assert "start recording a Room Session when one is started" in switch["description"], switch["description"]


    # the sessions list is where the id comes from, and the fixture is shaped like it
    code, session_props = response(spec, SESSIONS, "get")
    assert code == "200" and "id" in session_props, (code, sorted(session_props))
    assert set(found["data"][0]) <= set(session_props), sorted(set(found["data"][0]) - set(session_props))

    # and on what a recording is, on the list and on the get
    for path, method in ((f"{SESSIONS}/{{id}}/recordings", "get"), (f"{RECORDINGS}/{{id}}", "get")):
        code, props = response(spec, path, method)
        assert code == "200", (path, code)
        assert {"id", "room_session_id", "status", "duration", "format", "uri"} <= set(props), \
            (path, sorted(props))
        assert set(entry) <= set(props), (path, sorted(set(entry) - set(props)))
        params = [p["name"] for p in spec["paths"][path]["get"].get("parameters", [])
                  if p.get("in") == "query"]
        assert "media_ttl" in params, (path, params)
    code, props = response(spec, f"{RECORDINGS}/{{id}}", "delete")
    assert code == "204" and props == {}, (code, props)

    print(f"ok: POST {ROOMS} record_on_start=true, GET the sessions and the session's recordings, GET and DELETE "
          f"{RECORDINGS}/{REC[:8]}...; the spec documents the switch, the recording fields "
          f"and the 204")


if __name__ == "__main__":
    main()
