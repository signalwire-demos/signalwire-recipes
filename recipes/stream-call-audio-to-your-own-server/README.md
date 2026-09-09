# Stream call audio to your own server

> `tap` sends a copy of a call's audio to a WebSocket or RTP destination of yours, and `stop_tap` ends it by control id. The same pair exists mid-call over REST as `calling.tap` and `calling.tap.stop`.

**Scenario:** a workshop that wants every support call's audio on its own server, live

## What this demonstrates

The bundled schema describes `tap`'s `uri` as the "destination of the tap media
stream: rtp://IP:port, ws://example.com, or wss://example.com". `direction` is
`speak` "for what party says", `listen` "for what party hears", or `both`.
`codec` is PCMU or PCMA. `control_id` is the "identifier for this tap to use
with `stop_tap`". The bundled schema requires only `uri`. The vendored REST spec has the same
operation as the call command `calling.tap`. It takes a `tap` configuration of
type `audio` and a `device` of type `ws` or `rtp`, and `calling.tap.stop` ends
it. The SDK wraps those as `client.calling.tap` and `client.calling.tap_stop`.

## How it works

```yaml
- answer: {}
- tap:
    uri: "wss://media.example.com/tap"
    control_id: "workshop-tap"
    direction: "both"
    codec: "PCMU"
- connect:
    to: "+15550100001"
    timeout: 20
- stop_tap:
    control_id: "workshop-tap"
- hangup: {}
```

The document carries `tap` for both directions, then `connect`, then
`stop_tap` with the same control id. The Python surface builds the same document with `SWMLService` and
adds the REST pair:

```python
def start_tap(call_id):
    return client.calling.tap(call_id, control_id=CONTROL_ID,
                              tap={"type": "audio", "params": {"direction": "both"}},
                              device={"type": "ws", "params": {"uri": TAP_URI}})

def stop_tap(call_id):
    return client.calling.tap_stop(call_id, control_id=CONTROL_ID)
```

What the platform receives from `start_tap`:

```json
{"command": "calling.tap", "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"control_id": "workshop-tap",
            "tap": {"type": "audio", "params": {"direction": "both"}},
            "device": {"type": "ws", "params": {"uri": "wss://media.example.com/tap"}}}}
```

The spec describes the RTP device's `addr` as a "public IPv4 address" and says
"private/reserved ranges are rejected". It says the WebSocket `uri` "must start
with `ws://` or `wss://`".

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: TAP_URI, OWNER_NUMBER, credentials, basic-auth pair
python app.py
```

`TAP_URI` is a WebSocket server you run; the schema calls it the destination
of the tap media stream. The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/tap/` and call. To fork a call that is
already up, run `python -c "from app import start_tap; print(start_tap('<call_id>'))"`
from the `python/` folder.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

When you run it, you validate both surfaces, swap the SDK's HTTP layer for a
recorder, and assert the following.

- both surfaces contain `answer`, `tap`, `connect`, `stop_tap`, `hangup` in order and render the same document
- the `tap` object is exactly the wss URI, `both`, `PCMU` and the control id, and `stop_tap` repeats that id
- the bundled schema requires `uri` on `tap` and nothing else
- `start_tap` and `stop_tap` each make one `POST` to the documented calling path, and each body equals one expected object
- the vendored REST spec documents every `calling.tap` param and its nested `tap` and `ws` device, including their required fields and the `type` and `direction` enums
- the `calling.tap.stop` params are exactly the control id, and the vendored REST spec documents them and requires nothing more

## Limitations

You prove the documents and the requests. What arrives on your socket, and in
what framing, is the platform's side of a live call and belongs to the tap
documentation.

## What to change first

Change `direction` to `speak` in both surfaces and run the verifier. The `tap`
equality fails, which is the point: `speak`, `listen` and `both` are the three
choices, and the document names one.
