# Record a call

> The whole call is recorded in the background and the recording URL is delivered to a status URL.

**Scenario:** a support line that keeps a stereo recording of every conversation

## What this demonstrates

`record_call` starts a background recording and returns immediately, so the
verbs after it, including the `connect` that brings in the agent, run inside
the recording. The recording URL is not in the SWML response and not in the
call; it arrives at `status_url` when the recording finishes.

## How it works

```yaml
- answer: {}
- record_call:
    format: wav
    stereo: true        # caller on one channel, agent on the other
    direction: both
    status_url: "https://<your-host>/recording-status"
- play: { url: "say:This call is recorded for quality purposes." }
- connect: { to: "+1555..." }
```

Order matters: `record_call` before `connect`. The Python surface builds the
same document with `SWMLService` and adds a Flask route for `status_url` that
stores the URL only when `state` is `finished`.

Stopping early is `stop_record_call`; recordings are listed and deleted over
REST (`/api/relay/rest/recordings`). To send recordings to your own storage
instead of SignalWire's, see `export-recordings-and-enforce-retention`. That
path exists only in the Compatibility API's `<Record storageUrl>`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script, replace the number and
`status_url`, assign a phone number.

Python:

```bash
cd python
pip install -r requirements.txt
PUBLIC_URL=https://<your-host> AGENT_NUMBER=+1555... python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/record`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SWML schema. The verifier asserts `record_call`
precedes `connect`, records both directions in stereo and names a `status_url`, and
that the webhook stores a URL only for a finished recording.

## What to change first

Add `get-recording-consent-before-recording` in front: move `record_call` into
a tool result so recording starts only after the caller agrees.
