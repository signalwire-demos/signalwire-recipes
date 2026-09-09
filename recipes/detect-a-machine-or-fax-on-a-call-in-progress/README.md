# Detect a machine, fax tone or digits on a call in progress

> `calling.detect` starts detection on a call that is already up, from outside the call's document. One `detect` object picks what to listen for, and the result arrives at your webhook rather than in the response.

**Scenario:** your dialer answers a transferred call and needs to know whether a person, a voicemail or a fax machine is on the line

## What this demonstrates

Answering machine detection usually runs inside the document, before the call
says anything. This is the other case: the call is already up, and something
outside it wants to know who is there. Any process holding the call id can ask.

The vendored REST spec, `tools/openapi/rest.json`, is the authority for the
shape.

- `calling.detect` requires `control_id` and `detect`. The `detect` object is
  one of three configs, each requiring a `type` from the enum `machine`, `fax`
  or `digit`, and each with its own params.
- The spec's description says detection "runs asynchronously up to `timeout`
  seconds" and that results are "delivered via the `status_url` webhook", so
  the recipe refuses a detect with no status URL before it is sent.
- `calling.detect.stop` requires `control_id` and gives up early.

The machine params are where the classification lives:
`machine_voice_threshold` (1.25 seconds by default) and
`machine_words_threshold` (6 words) are what separate a greeting from a hello.
Fax detection takes a `tone` of `CED` or `CNG`, and digit detection takes the
digits you care about.

## How it works

```python
def machine(call_id, status_url, timeout=30, control_id=CONTROL_ID):
    _needs_status_url(status_url)
    params = {"machine_voice_threshold": 1.25, "machine_words_threshold": 6,
              "detect_message_end": True}
    detect = {"type": "machine", "params": params}
    return client.calling.detect(call_id, control_id=control_id, detect=detect,
                                 timeout=timeout, status_url=status_url)
```

What the platform receives:

```json
{"command": "calling.detect",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"control_id": "screening",
            "timeout": 30,
            "status_url": "https://your-host/detect-events",
            "detect": {"type": "machine",
                       "params": {"machine_voice_threshold": 1.25,
                                  "machine_words_threshold": 6,
                                  "detect_message_end": true}}}}
```

The SDK's `calling` namespace sends every call command to that one path and
puts the call id in `id`. The TypeScript SDK, `@signalwire/sdk`, does the same:
`client.calling.detect(callId, {...})` produces the body above.

The document-side version of this is
[Detect an answering machine](../detect-an-answering-machine/), which blocks
the call flow until it has an answer. The REST command does not block anything:
it listens while your code gets on with something else.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py machine <call_id> https://your-host/detect-events
python app.py fax <call_id> https://your-host/detect-events
python app.py stop <call_id>
```

The TypeScript surface is the same commands on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start machine <call_id> https://your-host/detect-events
```

Take the call id from a tool webhook, a status callback, or the `dial`
response. The `status_url` needs a public route of yours, because that is where
the result lands.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the four helpers,
and asserts the following.

- a detect with a missing or empty status URL raises before any request is made
- `calling.detect` requires `control_id` and `detect`, and its description names both the `timeout` behaviour and the `status_url` delivery
- the `detect` object is a `oneOf` of exactly the three documented configs, each requiring `type`, each carrying the same three-value enum
- the machine defaults in the spec are 4.5, 1, 1.25, 6, false and true, and the params this recipe sends are documented properties
- the fax tone enum is exactly `CNG`, `CED` and their lower-case forms
- `calling.detect.stop` requires only `control_id`
- each body equals the expected `{"command", "id", "params"}` shape
- the TypeScript surface sends those same four bodies and refuses the same detect

## Limitations

The verifier proves the requests, not the classification. Whether a given
voicemail greeting reads as a machine is the platform's judgement, tuned by
those thresholds.

One control id runs one detection. The spec says it must be unique per active
detect on the call, so two detections at once need two ids.

## What to change first

Change `"machine"` to `"voicemail"` in the `machine` helper and run the
verifier. The type is outside the enum every config shares, and the exact body
comparison fails, which is the point: three types are the whole vocabulary.
