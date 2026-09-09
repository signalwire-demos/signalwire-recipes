# Pause and resume a call recording over REST

> Four call commands share one `control_id`. `calling.record` starts a recording on a live call, `calling.record.pause` and `calling.record.resume` bracket the part you must not keep, and `calling.record.stop` ends it.

**Scenario:** your agent desktop pauses the recording while the caller reads a card number, then resumes it

## What this demonstrates

A recording does not have to be declared in the call's document. Any process
holding the call id can start one with `POST /api/calling/calls` and
`command: calling.record`, then pause, resume and stop it by the `control_id`
it chose. That is how an agent desktop with a Pause recording button works
when the call itself was set up somewhere else.

The vendored REST spec, `tools/openapi/rest.json`, is the authority for the
shapes.

- `calling.record` requires `control_id` and `record`, and `record` requires
  `audio`. The audio params include `stereo`, `direction`, `format` and
  `max_length`, where `0` means no limit.
- Three audio params decide when the recording stops on its own, and their REST
  defaults suit a voice prompt: `initial_timeout` 4 seconds, `end_silence_timeout`
  0.5 seconds, `terminators` `#`. Left alone they would end a call recording
  during the first pause. SWML's whole-call verb, `record_call`, defaults the
  same three to `0`, `0` and the empty string, and that is what this recipe
  sends.
- `calling.record.pause` requires `control_id` and takes a `behavior`: `skip`
  omits the paused audio from the file, `silence` replaces it with silence and
  keeps the timing.
- `calling.record.resume` and `calling.record.stop` require only `control_id`.

The verifier proves the five requests. The spec is the authority for what the
platform does with them.

## How it works

```python
CONTROL_ID = "agent-desk-recording"
WHOLE_CALL = {"initial_timeout": 0, "end_silence_timeout": 0, "terminators": ""}

def start(call_id, status_url=None):
    audio = {"stereo": True, "direction": "both", "format": "mp3", "max_length": 0,
             **WHOLE_CALL}
    params = {"control_id": CONTROL_ID, "record": {"audio": audio}}
    if status_url:
        params["status_url"] = status_url
    return client.calling.record(call_id, **params)

def pause(call_id):
    return client.calling.record_pause(call_id, control_id=CONTROL_ID, behavior="silence")
```

What the platform receives for `pause`:

```json
{"command": "calling.record.pause",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"control_id": "agent-desk-recording", "behavior": "silence"}}
```

The SDK's `calling` namespace, `rest/namespaces/calling.py`, sends every call
command to that one path and puts the call id in `id`. The control id is
yours to choose. It must be unique among the recordings active on the call,
and the same value carries through pause, resume and stop.

The spec says the HTTP response to `calling.record` returns the call leg and
not the recording URL. Pass a `status_url` to receive a webhook when the
recording finishes, with the final URL. Without one, the call's events endpoint
is where the URL turns up.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py start <call_id> https://your-host/recording-events
python app.py pause <call_id>
python app.py resume <call_id>
python app.py stop <call_id>
```

The TypeScript surface is the same four commands on `@signalwire/sdk`:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start start <call_id> https://your-host/recording-events
```

Take the call id from a tool webhook, a status callback, or the `dial`
response. There is no server to expose for the commands themselves. The
`status_url` is where the platform may send the URL of the finished recording.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the four helpers
plus a `start` with no status URL, and asserts the following.

- each helper adds exactly one `POST` to the documented calling path
- `calling.record` requires `control_id` and `record`, `record` requires `audio`, and every audio key sent is a documented `RecordAudioParams` property
- the sent `format` and `direction` are in the spec's enums
- the REST defaults for `initial_timeout`, `end_silence_timeout` and `terminators` are 4, 0.5 and `#`, the bundled SWML schema's `record_call` defaults them to 0, 0 and the empty string, and the recipe sends the second set
- `calling.record.pause` requires `control_id`, its `behavior` enum is exactly `skip` and `silence`, and the sent value is one of them
- resume and stop require only `control_id`
- each body equals the expected `{"command", "id", "params"}` shape, the five expected bodies all name one control id, and an omitted `status_url` is an absent key rather than a null
- the TypeScript surface, driven through the same recorder seam, sends those same five bodies

## Limitations

The verifier proves the requests, not the file. Whether the pause reads as a
gap of silence is what the finished recording shows.

Pausing the recording does not pause the call. The caller keeps talking; only
the file stops filling.

What a recording does at `initial_timeout: 0` is the platform's behaviour, not
something this recipe proves. The value is the one SWML uses for a whole-call
recording.

## What to change first

Change `PAUSE_BEHAVIOR` to `"skip"` and run the verifier. The exact body
comparison fails on `behavior`, which is the point: the two values produce
different files, and the verifier pins which one this recipe ships.
