# Stream call audio to a WebSocket that checks a bearer token

> `calling.stream` opens a TLS WebSocket to your endpoint and sends the call's audio down it. The connection carries a bearer token, one track or both, and whatever metadata you attach.

**Scenario:** your transcription service accepts connections only with a bearer token, and needs to know which ticket each stream belongs to

## What this demonstrates

`tap` copies a call's audio to a URI. `calling.stream` does the same job for
an endpoint that has opinions. It insists on TLS and authenticates. It lets you
pick a side of the conversation, and it hands your endpoint metadata when the
connection opens.

The vendored REST spec, `tools/openapi/rest.json`, is the authority.

- `calling.stream` requires `control_id` and `url`. The url "must start with
  `wss://` (TLS is required; plain `ws://` is rejected)", so the recipe refuses
  a `ws://` url before sending one.
- `track` is `inbound_track`, `outbound_track` or `both_tracks`.
- `authorization_bearer_token` is "included as `Authorization: Bearer <token>`
  when establishing the WebSocket connection".
- `custom_parameters` is an "arbitrary JSON object passed through to the
  WebSocket endpoint as connection metadata", which is how a stream says which
  ticket it belongs to.
- `status_url` receives the lifecycle webhooks, with `status_url_method` of
  `GET` or `POST`.
- `calling.stream.stop` requires `control_id`.

Use `tap` when the destination is an RTP address or a plain socket you control.
Use `stream` when the endpoint authenticates the connection, or when only one
side of the call should leave the platform.

## How it works

```python
def start(call_id, url, track="both_tracks", control_id=CONTROL_ID,
          status_url=None, tag=None):
    if not url.startswith("wss://"):
        raise ValueError(...)
    params = {"control_id": control_id, "url": url, "track": track,
              "codec": "PCMU", "name": "support"}
    if STREAM_TOKEN:
        params["authorization_bearer_token"] = STREAM_TOKEN
    if tag:
        params["custom_parameters"] = {"tag": tag}
    return client.calling.stream(call_id, **params)
```

What the platform receives:

```json
{"command": "calling.stream",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"control_id": "support-audio",
            "url": "wss://media.example.com/calls",
            "track": "both_tracks",
            "codec": "PCMU",
            "name": "support",
            "authorization_bearer_token": "…",
            "custom_parameters": {"tag": "ticket-4417"},
            "status_url": "https://media.example.com/stream-events",
            "status_url_method": "POST"}}
```

The token is read from the environment, so it is never a literal in the code
the page shows. Your endpoint checks the `Authorization` header on the upgrade
request and refuses anything else, which is the point of sending it.

`codec` is freeform in the spec, which lists `PCMU`, `PCMA` and `OPUS` as
common values. What your endpoint accepts is the real constraint.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py start <call_id> wss://media.example.com/calls
python app.py stop <call_id>
```

The TypeScript surface is the same two commands on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start start <call_id> wss://media.example.com/calls
```

Set `STREAM_BEARER_TOKEN` in `.env` to whatever your endpoint expects. Leave it
unset and the param is absent.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the helpers, and
asserts the following.

- a `ws://` url and an unknown track both raise before any request is made
- `calling.stream` requires `control_id` and `url`, and the spec's own text carries the TLS rule, the metadata rule and the `Authorization: Bearer` behaviour
- the track enum is exactly the three documented values, and the recipe's list matches it
- `status_url_method` is `GET` or `POST`
- the first body carries the token, the custom parameters and the status URL, and the second carries none of them, as absent keys rather than nulls
- `calling.stream.stop` requires only `control_id`
- the TypeScript surface sends those same three bodies and refuses `ws://` too

## Limitations

The verifier proves the requests, not the socket. Whether your endpoint accepts
the upgrade, and what it does with the audio, is yours to build.

The bearer token is sent to the platform in the clear inside the command body,
which is a TLS request to the API. Treat it as a credential your endpoint
issues, and rotate it like one.

## What to change first

Point `start` at a `ws://` url and run the verifier. It raises before the
request, which is the point. The spec rejects plain WebSocket, and the check
belongs in your code rather than in a 400.
