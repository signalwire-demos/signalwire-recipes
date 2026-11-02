# Manage video rooms over REST

> A video room is a Fabric Conference Room resource, and one REST family creates, lists, reads, updates and deletes it. A room per meeting is a create with a member cap and a join window; a meeting that is over is a delete.

**Scenario:** a booking system that opens a room before each appointment and closes it afterwards

## What this demonstrates

`create-a-video-room-and-join-from-the-browser` makes one room and joins it.
This recipe is the rest of a room's life. The vendored REST spec,
`tools/openapi/rest.json`, is the authority.

- `POST /api/fabric/resources/conference_rooms` requires `name` and
  `enable_room_previews`. `max_members` is 0 to 300. `join_from` and
  `join_until` bound when joining works, `remove_at` empties the room at a
  time, and `remove_after_seconds_elapsed` (0 to 200000) removes each
  participant that long after they joined.
- `GET` on the collection lists rooms, `GET .../{id}` reads one, and
  `GET /api/fabric/resources/conference_room/{id}/addresses` gives the address
  the browser dials.
- `PUT .../{id}` updates a room and requires `enable_room_previews` and
  `sync_audio_video` on every call, so the recipe reads the room first and
  sends its current values with the change. The read can return
  `sync_audio_video` as null and the update does not accept null, so an unset
  flag is sent as `false`.
- `DELETE .../{id}` answers `204`.

The SDKs wrap the five as `client.fabric.conference_rooms` in Python and
`client.fabric.conferenceRooms` in TypeScript. The helpers refuse a cap or a
removal delay outside the spec's bounds before any request, because the
platform would answer `422`.

## How it works

```python
def create_room(name, max_members=None, join_from=None, join_until=None, remove_at=None):
    body = {"name": name, "display_name": name, "enable_room_previews": False}
    if max_members is not None:
        body["max_members"] = _bounded("max_members", max_members, MAX_MEMBERS)
    ...
    return client.fabric.conference_rooms.create(**body)

def update_room(room_id, **changes):
    current = get_room(room_id)["conference_room"]
    body = {"enable_room_previews": current["enable_room_previews"],
            "sync_audio_video": current["sync_audio_video"], **changes}
    return client.fabric.conference_rooms.update(room_id, **body)   # a PUT
```

What the platform receives for a room that opens at 08:50, locks at 09:30 and
empties at 10:00:

```json
POST /api/fabric/resources/conference_rooms
{"name": "standup-0900", "display_name": "standup-0900", "enable_room_previews": false,
 "max_members": 12, "join_from": "2026-11-03T08:50:00Z",
 "join_until": "2026-11-03T09:30:00Z", "remove_at": "2026-11-03T10:00:00Z"}
```

The response carries the room's `id`, which the other four calls take. Its
address is `/public/<name>`, and the addresses call confirms it.

## Run it

```bash
cd python && pip install -r requirements.txt
cp ../.env.example .env
python app.py create standup-0900 --members 12 --opens 2026-11-03T08:50:00Z \
    --closes 2026-11-03T09:30:00Z --ends 2026-11-03T10:00:00Z
python app.py list
python app.py update <room_id> --members 20
python app.py delete <room_id>
```

The TypeScript surface takes the same commands, on Node 20.18.1 or newer:

```bash
cd typescript && npm ci && cp ../.env.example .env
npm start create standup-0900 12 2026-11-03T08:50:00Z 2026-11-03T09:30:00Z
```

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, the verifier asserts:

- the helpers make the nine documented requests in order: POST, GET the collection, GET one, GET its addresses, GET then PUT twice, DELETE
- the create body is exactly `name`, `display_name`, `enable_room_previews`, the cap and the three times, and every key is documented
- the spec requires `name` and `enable_room_previews` on a create, and the three times are `date-time` fields
- the bounds the helpers refuse at equal the spec's `minimum` and `maximum` for `max_members` and `remove_after_seconds_elapsed`
- the PUT carries the two fields the spec requires on every update, read back from the room, plus the change
- the read schema lets `sync_audio_video` be null and the update schema does not, and a room read back with it null is updated with `false`
- a cap above the maximum raises before any request
- the TypeScript surface sends the same nine requests with the same bodies, reads the `204`, and refuses the same cap

## Limitations

The verifier proves the requests, not the room. The spec says joining before
`join_from` "will result in failure to join"; what a browser sees at that
moment is live behaviour. What happens to participants when a room is deleted
while they are in it is not documented, so use `remove_at` to end a session.
Who was in a room and when is the room sessions API, `/api/video/room_sessions`,
which this recipe does not touch.

## What to change first

Pass `record_on_start=True` to `create_room` so every session of the room is
recorded, then read the recordings with `record-a-video-room`.
