# Whisper a summary to the agent before connecting the caller

> The agent knows who is calling before the caller can hear them.

**Scenario:** an intake line that hands warm calls to a person

## What this demonstrates

The receiving agent picks up and hears a short briefing about the caller. Only then
are the two legs joined. The caller hears hold audio throughout and never hears
the briefing.

This is the difference between a transfer and a handoff. A transfer moves a
call; a handoff moves a call and what is known about it.

## How it works

`connect` takes a `confirm`, which runs on the answering leg after it picks up
and before the bridge completes.

```json
{"connect": {
  "to": "+15550100001",
  "confirm": [{"play": {"url": "say:Call from Dana about a refund."}}],
  "confirm_timeout": 20
}}
```

`confirm` takes either a URL returning a document or an array of SWML methods
inline. Inline is right here, because the briefing is built from state the
agent already holds and there is nothing to fetch.

Placement is the whole mechanism. The same `play` in `main` would be heard by
the caller, because `main` is the call. Inside `confirm` it belongs to the leg
being dialled.

`FunctionResult.connect()` takes no `confirm`, so the verb is built by hand and
handed over with `execute_swml`. That is the same shape `transfer-a-call-without-losing-context` uses. It is also why
the verifier asserts JSON keys rather than the SDK method behind them.

The briefing is assembled from a fixed tuple of fields. Which of them reach a
colleague is decided in code, not by the model. That excludes fields outside
`BRIEFED`. It does not redact anything inside them: whatever the model put in `reason`
is read aloud as it stands.

A transfer with nothing collected is refused. An agent who answers to silence
after being promised a briefing is worse off than one who was never promised
anything.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at
`https://<user>:<password>@<your-host>/intake/`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and runs the handler, asserting:

- nothing in the document connects; only the handler does
- the emitted `connect` carries the briefing inside `confirm`, with a timeout
- the connect is the whole of the emitted SWML, so nothing plays to the caller
- the three chosen fields are spoken, and two sensitive ones in the same state
  are not
- a missing field degrades the sentence instead of breaking it
- three incomplete intakes are refused rather than transferred

## Limitations

`confirm` is one-way. The agent hears the briefing and cannot answer it, so
there is no accept or reject here. Making the handoff refusable means a
`prompt` inside the confirm and a branch on the result.

`confirm_timeout` bounds how long the platform waits. A briefing longer than it
is cut off, and a long summary is the usual cause.

## What to change first

Move the `play` out of `confirm` and into `main`, immediately before the `connect`.
The briefing is now read to the caller, who learns what you think their reason is. Put
it after the `connect` instead and it does not play at all until the far leg ends.
