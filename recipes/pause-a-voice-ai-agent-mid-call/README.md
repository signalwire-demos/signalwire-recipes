# Pause a voice AI agent mid-call and bring it back

> Three REST commands act on the AI running a call, not on the call itself. `calling.ai_hold` holds the caller after the agent says a line, `calling.ai_unhold` brings it back, and `calling.ai.stop` ends the AI while the call keeps running.

**Scenario:** your backend needs a moment to finish a lookup, and the agent should stop listening until it is done

## What this demonstrates

An agent waiting on something slow has two bad options. It can talk through
the wait, or sit silent while the model tries to fill the gap. This is the
third: your backend holds the caller, does the work, and takes them off hold.

The vendored REST spec, `tools/openapi/rest.json`, is the authority.

- `calling.ai_hold` takes a `prompt`, which the spec describes as "a system
  message added to the AI conversation before placing the caller on hold. The
  AI will speak this message to the caller before hold music begins." It also
  takes a `timeout`.
- `calling.ai_unhold` takes no params at all.
- `calling.ai.stop` documents one param, `control_id`, and calls it "Reserved
  field ... currently ignored", so this recipe does not send it.

**The timeout is a string.** The spec types it as one and says so twice: "must
be sent as a string" and "integer payloads are rejected". A number here is a
400, so the recipe converts, and refuses a fractional value rather than
rounding one silently.

## How it works

```python
def hold(call_id, seconds=90, prompt=HOLD_PROMPT):
    if int(seconds) != float(seconds):
        raise ValueError(...)
    return client.calling.ai_hold(call_id, timeout=str(int(seconds)), prompt=prompt)

def stop(call_id):
    # the method is ai_stop; the command on the wire is calling.ai.stop
    return client.calling.ai_stop(call_id)
```

What the platform receives for `hold`:

```json
{"command": "calling.ai_hold",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"timeout": "90",
            "prompt": "Let me check that for you. One moment."}}
```

The method name and the command are not the same word. `ai_stop()` sends
`calling.ai.stop`, with a dot, in both SDKs. That is the usual rule here: the
key the platform receives is what a verifier asserts, never the name of the
method that produced it.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py hold <call_id> 90
python app.py unhold <call_id>
python app.py stop <call_id>
```

The TypeScript surface is the same three commands on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start hold <call_id> 90
```

Take the call id from the agent's own tool webhook, which carries it as
`call_id`. There is no server to expose.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the three
helpers, and asserts the following.

- a fractional hold raises before any request is made
- the spec types `ai_hold`'s `timeout` as a string, and its description says both that it must be sent as one and that integers are rejected
- what the recipe sent is a string, and it is the number of seconds it was given
- `calling.ai_unhold` documents no params, and none are sent
- `calling.ai.stop` documents `control_id` as reserved and ignored, and the recipe sends empty params
- each body equals the expected `{"command", "id", "params"}` shape, and the third one carries `calling.ai.stop` rather than the method's name
- the TypeScript surface sends those same three bodies, with the timeout as a string

## Limitations

The verifier proves the requests, not the hold. What the caller hears while
held, and how the agent picks the conversation back up, are live behaviour.

`calling.ai.stop` ends the AI, not the call. Whatever is left in the document
after the `ai` verb is what happens next. On a document that was only an agent,
that is the end of the call.

## What to change first

Pass `timeout=90` instead of `timeout=str(90)` in `hold` and run the verifier.
The string assertion fails, which is the point: this is the one param in the
recipe where the JSON type is the whole rule.
