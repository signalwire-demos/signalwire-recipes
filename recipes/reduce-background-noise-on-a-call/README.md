# Reduce background noise on a call

> `denoise` switches noise reduction on for a leg and `stop_denoise` switches it off, in SWML or mid-call over REST as `calling.denoise` and `calling.denoise.stop`.

**Scenario:** a caller leaving a message from a busy workshop floor

## What this demonstrates

Noise reduction is a switch, not a setting. In SWML, the `denoise` verb starts
it and `stop_denoise` stops it; the bundled schema gives both an empty object
and describes `denoise` as "Start noise reduction. You can stop it at any time
using `stop_denoise`". Over REST, the vendored spec has the same pair as call
commands, `calling.denoise` and `calling.denoise.stop`, addressed to a live
call by `id` with empty `params`. The SDK wraps those as `client.calling.denoise`
and `client.calling.denoise_stop`.

## How it works

```yaml
- answer: {}
- denoise: {}
- play: { url: "say:Leave your message after the tone." }
- record: { beep: true, max_length: 60, terminators: "#" }
- stop_denoise: {}
- play: { url: "say:Thanks. Goodbye." }
- hangup: {}
```

Noise reduction is on while the caller records and off for the goodbye. The
Python surface builds the same document with `SWMLService`, and adds two
helpers for the REST side:

```python
def quiet(call_id):
    return client.calling.denoise(call_id)

def loud(call_id):
    return client.calling.denoise_stop(call_id)
```

What the platform receives from `quiet`:

```json
{"command": "calling.denoise", "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f", "params": {}}
```

`params` is empty because the spec's variant has no properties; `id` is the
call's id.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, and the basic-auth pair
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/denoise/`. To toggle mid-call from your
backend instead, call `quiet(call_id)` and `loud(call_id)` from a Python shell
with a live call's id.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

It validates both surfaces, swaps the SDK's HTTP layer for a recorder, and
asserts the following.

- both surfaces run `answer`, `denoise`, `play`, `record`, `stop_denoise`, `play`, `hangup`, in that order, and render the same document
- `denoise` and `stop_denoise` each carry an empty object, and the bundled schema gives both no parameters
- `quiet` and `loud` each make exactly one `POST` to the documented calling path, measured with a fresh recorder per helper
- each body is exactly the command, the call `id` at the top level, and empty `params`
- the spec's variants for both commands require `command`, `id` and `params` and define no param properties

## Limitations

The verifier proves the documents and the requests. What noise reduction does
to the audio is the platform's processing on a live call.

## What to change first

Move `stop_denoise` above `record` in both surfaces and run the verifier. The
order assertion fails, which is the point: the switch is on exactly between the
two verbs, and the recording sat between them.
