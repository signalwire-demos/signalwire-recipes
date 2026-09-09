# Add a phone caller to a video room

> You create a conference room over REST with the two fields the spec requires. A SWML `join_room` naming that room is the verb that puts the leg running the document into it.

**Scenario:** a workshop stand-up on video that the mechanic on the road joins by phone

## What this demonstrates

Two pieces. `POST /api/fabric/resources/conference_rooms` creates the room; the
vendored REST spec requires `name` and `enable_room_previews` and takes
`display_name`, `max_members`, `layout`, `record_on_start` and a dozen more as
options. The SDK wraps it as `client.fabric.conference_rooms.create`. In SWML,
`join_room` takes `name`, its one required field per the bundled schema, and
the bundled schema describes the verb as joining the named room.

## How it works

```python
def create_room(name=ROOM):
    return client.fabric.conference_rooms.create(
        name=name, display_name="Workshop stand-up", enable_room_previews=False,
        max_members=10)
```

```yaml
- answer: {}
- play: { url: "say:Joining the workshop stand-up. One moment." }
- join_room:
    name: "workshop-standup"
- hangup: {}
```

What the platform receives for the room:

```json
POST /api/fabric/resources/conference_rooms
{"name": "workshop-standup", "display_name": "Workshop stand-up",
 "enable_room_previews": false, "max_members": 10}
```

`hangup` follows `join_room` in the document. The Python surface builds the same
document with `SWMLService` and reads the room name from `ROOM_NAME`, so the
REST call and the verb agree by construction.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, ROOM_NAME and the basic-auth pair
python app.py create-room        # once
python app.py                    # then serve the document
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/join/`. Have the browser participants
join the room by its address, then call the number.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier swaps the SDK's HTTP layer for a recorder, validates both surfaces,
and asserts the following.

- `create_room` makes one `POST` to the documented conference rooms path
- the spec's required list for that call is exactly `name` and `enable_room_previews`, both present, and the spec documents every field sent
- the body equals one expected object: `name`, `display_name`, `enable_room_previews` false and `max_members` 10, and `name` is the room the document joins
- both surfaces contain `answer`, `play`, `join_room`, `hangup` in order, `join_room` carries exactly `{"name": "workshop-standup"}`, and the two documents are equal
- the bundled schema requires `name` on `join_room` and nothing else

## Limitations

The verifier proves the request and the document. What the phone participant
hears, and how the room lays them out, are the platform's side of a live call.

This recipe covers the phone leg only. For browser participants, see
`create-a-video-room-and-join-from-the-browser`.

## What to change first

Change the `name` in `swml/agent.yaml` to another room and run the verifier.
The REST body and the Python document pass, because the verifier's preset
`ROOM_NAME` takes precedence over `.env`. The YAML `join_room` check fails
against the verifier's fixed room. The verifier holds the REST body and both
documents to one value, and a surface that drifts fails on its own.
