# Add a group chat to a video room

> Everyone in a video room shares one text thread, and the thread outlives the call. The browser reads and writes it through the room's address with a token your server mints.

**Scenario:** a team stand-up room where someone joining late reads what was typed before they arrived

## What this demonstrates

In a room call the Browser SDK v4 exposes the room as `call.address`. Text sent
to that address reaches everyone in the room's conversation. The room keeps one
thread across sessions, per the
[Messaging and chat guide](https://signalwire.com/docs/browser-sdk/v4/guides/messaging-chat).
A group chat is not a second service with a second token. It is the room's own
conversation, read and written by the client that already carries the video.

Two pieces. A Flask route mints a Subscriber Access Token per user with
`POST /api/fabric/subscribers/tokens`. Each message carries a `fromAddress$`,
the sender's address, so the token decides who a message is from. The page
dials the room with audio and video, subscribes to `call.address$`, reads
`textMessages$` and posts with `sendText()`.

## How it works

Server (`python/app.py`):

```python
client.fabric.tokens.create_subscriber_token(reference=user_id, display_name="Dana")
```

Browser (`typescript/index.ts`):

```ts
const call = await client.dial("/public/team-standup", { audio: true, video: true });
call.address$.subscribe((address) => {
  address?.textMessages$.subscribe((thread) => {
    thread?.values$.subscribe(render);        // the room's thread
    thread?.hasMore$.subscribe(...);           // older pages, via loadMore()
  });
  send.onclick = () => address?.sendText(input.value);
});
```

`textMessages$` emits a collection: `values$` is the messages, `hasMore$` says
whether older pages exist and `loadMore()` fetches one. The guide's example uses
one Subscriber Access Token per person. It notes that one token in two tabs logs
stale-event errors, so the server mints one per `reference`.

## Run it

```bash
cd python && pip install -r requirements.txt
cp ../.env.example .env            # space, project, token, ROOM_NAME
python app.py

cd ../typescript && npm ci && npm start   # Vite serves index.html and proxies /token to :8080
```

`typescript/index.html` carries the video slot and the chat controls, and
`vite.config.ts` forwards `/token` to the Flask app, so the page and the server
share one origin. Open the page twice with different `?user=` and `?name=`
values to see two people in one thread. The room has to exist first;
`create-a-video-room-and-join-from-the-browser` creates it.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, the verifier asserts:

- the route makes one POST to `/api/fabric/subscribers/tokens` with `reference` and `display_name`, and every field sent is documented
- the response carries the minted token and the room's address, never the project API token
- a request naming no user is a 400 and sends nothing
- the page dials the destination and uses `call.address$`, `textMessages$`, `values$`, `hasMore$`, `loadMore()` and `sendText()`
- `index.html` loads the script and carries every element the script looks up, and the dev server forwards `/token`
- with `typescript/node_modules` present, the page type-checks against the installed Browser SDK

## Limitations

The Browser SDK this uses is a release candidate, `4.0.0-rc.2`. `sendText()`
resolves when the platform accepts the message; there is no delivered or read
signal, so that state is yours to keep if you need it. The guide documents the
thread with Subscriber Access Tokens. Whether a Guest token can post to it is
not documented, so this recipe does not claim it. A private message between two
participants goes to that participant's own address, which the page does not
show. The verifier proves the token request and the page's use of the
documented members; what the thread does on a live call is live behaviour.

## What to change first

Subscribe to each message's `fromAddress$` and render its `displayName` beside
the text, so the log shows who typed. Then give the token an `expire_at` a few
minutes out and let the page refresh it, which is `call-from-a-browser`'s job.
