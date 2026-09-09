# Create a video room and join from the browser

> A room is created over REST, a token is minted per participant, and the browser joins with layouts and screen share.

**Scenario:** a team stand-up room on your own page

## What this demonstrates

A video room is a Fabric *Conference Room* resource: one REST call creates it
and gives it an address, `/public/<name>`. A participant needs no account, because your server mints a Guest token pinned to that
one address. The browser uses the Browser SDK v4 to dial it with audio and video. SignalWire's video is an
MCU, so each participant receives one mixed stream; layouts and screen share are
call-level controls.

## How it works

Server (`python/app.py`):

```python
client.fabric.conference_rooms.create(name="team-standup", max_members=25, layout="grid-responsive",
                                      quality="720p", record_on_start=False, enable_room_previews=True)
client.fabric.tokens.create_guest_token(allowed_addresses=["/public/team-standup"])
```

Browser (`typescript/index.ts`):

```ts
const { token, destination } = await (await fetch("/token", { method: "POST", ... })).json();
const client = new SignalWire(new StaticCredentialProvider({ token }));
await client.connect();
const call = await client.dial(destination, { audio: true, video: true });
call.remoteStream$.subscribe((s) => { if (s) video.srcObject = s; });
call.setLayout({ name: "grid-responsive" });     // layouts
call.self.startScreenShare();                    // screen share
```

The Guest token can dial only the room, and the project API token never leaves
the server. A signed-in user would get a Subscriber Access Token instead
(`call-from-a-browser`), which can also receive calls. Adding a phone caller to
the same room is `add-a-phone-caller-to-a-video-room`; recording and RTMP are
their own REST controls (`record-a-video-room`, `stream-a-video-room-to-rtmp`).

## Run it

```bash
cd python && pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... ROOM_NAME=team-standup
python app.py
curl -X POST localhost:8080/rooms -H 'content-type: application/json' -d '{"name": "team-standup"}'

cd ../typescript && npm ci && npm start     # serve index.ts with a page that has #room, #layout, #share, #leave
```

Proxy `/token` from the page to the Flask app (or serve both from one origin).

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, the two routes must make the documented
`conference_rooms` and `guests/tokens` requests, checked against
`tools/openapi/rest.json`. The verifier also asserts:

- the required `enable_room_previews` is present
- the token's `allowed_addresses` is exactly the room's address
- the project token never appears in the response
- the TypeScript client connects and dials with the documented calls

When `typescript/node_modules` is present the client is also type-checked with `tsc`.

## What to change first

Mint the token with an `expire_at` a few minutes out, and turn `record_on_start`
on to get a recording of every session.
