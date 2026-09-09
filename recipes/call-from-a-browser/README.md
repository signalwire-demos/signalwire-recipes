# Call from a browser

> A page dials a phone number or Resource address over WebRTC with a token your server minted.

**Scenario:** a "call us" button inside a logged-in web app

## What this demonstrates

WebRTC calling needs two things a static page cannot hold: a credential and a
destination. A small server mints a Subscriber Access Token for the signed-in user (`POST
/api/fabric/subscribers/tokens`). The Browser SDK v4 connects with that token and
dials a phone number, or a Fabric address such as `/public/support`. A Fabric address
can land on a SWML script, an AI agent or another subscriber. The project API
token never leaves the server.

## How it works

Server (`python/app.py`):

```python
client.fabric.tokens.create_subscriber_token(reference=user_id, display_name="Dana")   # -> {"token": ..., "refresh_token": ...}
```

Browser (`typescript/index.ts`):

```ts
const { token, destination } = await (await fetch("/token", { method: "POST", ... })).json();
const client = new SignalWire(new StaticCredentialProvider({ token }));
await client.connect();
const call = await client.dial(destination, { audio: true, video: false });
call.remoteStream$.subscribe((s) => { if (s) audio.srcObject = s; });
call.state$.subscribe((state) => status.textContent = state);
```

A Subscriber Access Token identifies one user and can also *receive* calls
after `client.register()`. See `receive-calls-in-the-browser`. For an anonymous visitor who should reach exactly one destination, mint a Guest token
instead (`get-a-webrtc-token-with-restricted-dial-targets`). For a button with no
backend at all, use the embeddable widget (`embed-a-call-widget-with-no-backend`).
Tokens expire; the companion `refresh_token` is how a long session rolls over.

## Run it

```bash
cd python && pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... DIAL_DESTINATION=/public/support
python app.py

cd ../typescript && npm ci && npm start     # a page with #status, #mute, #hangup; proxy /token to the Flask app
```

Open the page with `?to=+15551234567` to dial a phone number instead.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, the verifier asserts both halves:

- `/token` makes one documented POST to `/api/fabric/subscribers/tokens` with
  the required `reference`, checked against `tools/openapi/rest.json`
- that route returns only the minted token
- the TypeScript client fetches its token from the server, connects, and dials
  with the documented v4 calls

When `typescript/node_modules` is present the client is also type-checked with `tsc`.

## What to change first

Set `DIAL_DESTINATION` to the address of an AI agent (`route-a-call-to-an-ai-agent`)
and the button talks to the agent instead of a person.
