# Play a prompt and collect digits or speech over REST

> `calling.play` speaks text or plays a file into a live call, `calling.play.stop` cuts it short, and `calling.collect` gathers keypad digits or speech. The result does not come back in the HTTP response; the platform posts it to the `status_url` you give.

**Scenario:** your agent desktop asks the caller to key in an account number while the human agent stays on the line

## What this demonstrates

Prompting a caller and reading their answer is usually written into the call's
document. The same two operations exist as REST commands. A process that holds
the call id can run them on a call it did not set up. The vendored REST spec,
`tools/openapi/rest.json`, is the authority for the shapes.

- `calling.play` requires `control_id` and `play`, an ordered list of items.
  Each item has a `type`, one of `audio`, `tts`, `silence` or `ringtone`, and
  `params`. A `tts` item requires `text`; an `audio` item requires `url`.
- `calling.play.stop` requires `control_id`, the id you gave the play.
- `calling.play.volume` requires `control_id` and `volume`, a dB adjustment the
  spec bounds to "between -40 and 40". The recipe refuses anything outside it.
- `calling.collect` requires `control_id` and, in the spec's words, "at least
  one of `digits` or `speech`". `digits` requires `max`. Results are
  "delivered asynchronously via the `status_url` webhook", so the recipe
  refuses a collect with no status URL before it is sent.
- `start_input_timers` defaults to `false`, and then `initial_timeout` does not
  start counting. Both collects send `true`. Send `false` instead when the
  prompt is still playing, and start the clock yourself with
  `calling.collect.start_input_timers` for the same `control_id`.

The verifier proves the six requests and the refusal. The spec is the
authority for what the platform does with them.

## How it works

```python
def say(call_id, text, control_id=PLAY_ID, status_url=None):
    item = {"type": "tts", "params": {"text": text}}
    params = {"control_id": control_id, "play": [item]}
    if status_url:
        params["status_url"] = status_url
    return client.calling.play(call_id, **params)

def ask_digits(call_id, status_url, max_digits=10, control_id=COLLECT_ID):
    _needs_status_url(status_url)
    digits = {"max": max_digits, "terminators": "#", "digit_timeout": 5}
    return client.calling.collect(call_id, control_id=control_id, digits=digits,
                                  initial_timeout=10, start_input_timers=True,
                                  status_url=status_url)
```

What the platform receives for `ask_digits`:

```json
{"command": "calling.collect",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"control_id": "agent-desk-input",
            "initial_timeout": 10,
            "digits": {"max": 10, "terminators": "#", "digit_timeout": 5},
            "start_input_timers": true,
            "status_url": "https://your-host/collect-events"}}
```

The SDK's `calling` namespace, `rest/namespaces/calling.py`, sends every call
command to that one path and puts the call id in `id`. Each operation gets its
own control id, and the matching stop command names it.

The spec documents what arrives at `status_url`. A digit result has the shape
`{control_id, call_id, node_id, result: {type: "digit", params: {digits,
terminator}}}`; a speech result carries `{type: "speech", params: {text,
confidence}}`. Playback events carry a `state` of `playing`, `paused`,
`finished` or `error`. The route that receives them is an ordinary webhook
handler, the same shape as the one in Handle call status callbacks.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py say <call_id> "Please key in your account number, then press pound."
python app.py digits <call_id> https://your-host/collect-events
python app.py speech <call_id> https://your-host/collect-events
python app.py volume <call_id> -6
python app.py stop <call_id>
```

The TypeScript surface is the same commands on `@signalwire/sdk`:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start digits <call_id> https://your-host/collect-events
```

Take the call id from a tool webhook, a status callback, or the `dial`
response. The commands need no server of yours. The `status_url` does: it is
where the collected digits or text arrive, so point it at a public route that
logs the body.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls every helper, and
asserts the following.

- a collect with a missing or empty status URL raises before any request is made
- each helper adds exactly one `POST` to the documented calling path
- a play is sent with and without `status_url`, and the key is absent when it is not given
- `calling.play` requires `control_id` and `play`, the item type enum is exactly the four types, and each item type is pinned to its own required param: `text` for `tts`, `url` for `audio`, `duration` for `silence`
- the spec's `calling.play` description names the four playback states, and its `calling.collect` description says results are delivered to the `status_url` webhook
- `calling.collect` requires only `control_id`, `digits` requires `max`, and every sent `digits` and `speech` key is documented
- the spec defaults `start_input_timers` to `false`, and both collects send `true`
- the two stop commands require only `control_id`, and `calling.play.volume` requires the control id and a volume, with the range in the spec's own text
- a volume outside -40 to 40 raises before any request is made, as does one that is not a number, in both the value a caller passes and the string the command line hands over
- each body equals the expected `{"command", "id", "params"}` shape, and every param is a documented property
- the TypeScript surface sends those same seven bodies, and refuses a collect with no status URL before any request

## Limitations

The verifier proves the requests, not the audio or the recognition. What the
caller hears, and what `text` the speech engine returns, are live behaviour.

The recipe gives the play and the collect fixed control ids. Two prompts
playing at once on one call need two ids; the spec says the id must be unique
per active play on the call.

## What to change first

Change `"tts"` in `say` to `"speech"` and run the verifier. The item type is
outside the spec's enum and the exact body comparison fails, which is the
point: the four item types are the whole vocabulary.
