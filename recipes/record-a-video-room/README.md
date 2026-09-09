# Record a video room

> `record_on_start: true` on a room makes the platform record each of its sessions. A session's recordings list over REST, each with a `uri`, a `status` and a `duration`, and a DELETE by recording id asks the platform to delete one and answers `204`.

**Scenario:** a workshop stand-up on video that the people who missed it watch later

## What this demonstrates

Recording is a property of the room, not a button in the call. The vendored
REST spec's `POST /api/video/rooms` takes `record_on_start`, a boolean. The
spec describes it as "Specifies whether to start recording a Room Session when
one is started for this Room". From then on the recordings are REST objects.
`GET /api/video/room_sessions/{id}/recordings` lists a session's, and each
carries `status`, `duration`, `format`, `size_in_bytes` and a `uri`.
`GET /api/video/room_recordings/{id}` reads one, and
`DELETE /api/video/room_recordings/{id}` asks for its deletion and answers `204`. You
reach them as `client.video.rooms.create`,
`client.video.room_sessions.list_recordings`, and `client.video.room_recordings`
`get` and `delete`.

## How it works

```python
def create_room(name=ROOM):
    return client.video.rooms.create(name=name, display_name="Workshop stand-up",
                                     record_on_start=True)

def recordings_of(session_id):
    return client.video.room_sessions.list_recordings(session_id)

def delete_recording(recording_id):
    return client.video.room_recordings.delete(recording_id)
```

What the platform receives:

```json
POST /api/video/rooms
{"name": "workshop-standup", "display_name": "Workshop stand-up", "record_on_start": true}

GET /api/video/room_sessions/<session_id>/recordings
GET /api/video/room_recordings/<recording_id>
DELETE /api/video/room_recordings/<recording_id>
```

Read the session id from `GET /api/video/room_sessions`, which the SDK exposes
as `client.video.room_sessions.list`. The recordings list and the get both
document a `media_ttl` query parameter; the recipe leaves it at the platform's
default.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py room               # once
python app.py sessions           # after a session: the ids to ask about
python app.py recordings <session_id>
python app.py get <recording_id>
python app.py delete <recording_id>
```

There is no server to expose; the script speaks to the REST API and exits. To
hold a session, join the room from a browser the way
`create-a-video-room-and-join-from-the-browser` does, then leave. Then list the
session's recordings and read each one's `status`.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder that answers with a room, one
session and one recording. You call the five helpers and assert the following.

- they make five requests in order: `POST` the room, `GET` the sessions, `GET` the session's recordings, `GET` one recording, `DELETE` it
- the room body is exactly `name`, `display_name` and `record_on_start: true`, and the other four carry no body and no query
- every path and body is documented; the spec requires `name` on the room and describes `record_on_start` with the quoted sentence
- the sessions list's documented items carry `id`, and the fixture session uses only documented fields
- the spec's recording schema, on both the list and the get, carries `id`, `room_session_id`, `status`, `duration`, `format` and `uri`
- the recording fixture uses only fields each of those two schemas documents
- the delete answers `204` with no body, and both the list and the get document `media_ttl`

## Limitations

You prove the requests and the documented shapes. When a recording reaches
`completed`, and what the `uri` serves, are the platform's side of a live
session.

Do not look here for starting a recording from inside the call. The Browser
SDK v4 reference labels `startRecording` unimplemented, so the room property is
the documented switch.

## What to change first

Drop `record_on_start=True` from `create_room` and run the verifier. The
exact-body assertion fails, and nothing else would. A room without the switch
asks for no automatic recording; the spec documents no default for the field,
so the platform's own is what you get.
