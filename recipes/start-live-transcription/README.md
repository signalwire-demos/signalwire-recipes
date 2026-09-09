# Start live transcription

> Partial and final transcripts of both legs arrive at your webhook while the call is still in progress, and a summary when it ends.

**Scenario:** a meeting line that streams captions to a browser and mails a summary afterwards

## What this demonstrates

`live_transcribe` is a call-level verb, independent of any AI agent. Started before `connect`, it transcribes both legs of the bridged conversation. It
POSTs partial events while `live_events` is on, and a final event per utterance
carrying the leg it came from. When the session ends, `ai_summary` adds an AI-written
summary. Stopping (`action:
stop`) and summarising on demand (`action: summarize`) are the same verb.

## How it works

```yaml
- answer: {}
- live_transcribe:
    action:
      start:
        webhook: "https://<your-host>/transcript"
        lang: en
        live_events: true
        ai_summary: true
        direction: [remote-caller, local-caller]
        speech_engine: deepgram
- connect: { to: "+1555..." }
```

The Flask route at `/transcript` keeps finals per call (with the leg), keeps
the summary, and drops partials, where a caption display would render them
instead. The same session can be started on a live call over REST
(`calling.live_transcribe`) or from RELAY.

A call has one transcriber, so `live_transcribe` cannot run alongside `ai_sidecar`.
For a whole-call transcript delivered once at the end rather than a stream, use
`transcribe-a-call-in-the-background`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script, set `webhook` and the
destination number, assign a phone number.

Python:

```bash
cd python
pip install -r requirements.txt
PUBLIC_URL=https://<your-host> AGENT_NUMBER=+1555... python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/transcribe`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SWML schema. The verifier asserts `live_transcribe`
precedes `connect` with `live_events`, `ai_summary` and both directions on, and that
the webhook keeps finals and the summary while dropping partials.

## What to change first

Push the finals to a browser over WebSocket for live captions. Alternatively, feed
them to `classify-sentiment`-style logic to raise a supervisor alert mid-call.
