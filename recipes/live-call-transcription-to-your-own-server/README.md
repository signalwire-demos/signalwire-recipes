# Live call transcription line: every word posted to a server you own, with no model in the call path

> A transcription line demo built to show live_transcribe sending every utterance to your own authenticated webhook. The SWML has no ai verb, viewers get a read-only login, and the payload adapter is the one place that knows the event shape.

**Scenario:** A caller dials in and talks; each utterance is posted to your endpoint, stored per call and re-broadcast over Server-Sent Events

## What this demonstrates

The transcript goes to your code first, and the call flow is code, not a
prompt. `build_swml()` starts `live_transcribe` straight after `answer`, before
the caller hears anything, and points its webhook at your own authenticated
endpoint. The SWML has no `ai` verb: no model is in the call path, and nothing
reads the transcript before it lands in your storage. Every consumer route
needs a login, and there are two. The SWML basic auth is the platform's: it
alone can POST `/transcript`, list every call at `/calls`, and stream all calls
from `/events`. The optional viewer login reads one call it names and is
refused everywhere else, so a viewer cannot forge segments or browse other
calls.

The caller dials the line and hears one sentence saying it is transcribed.
From that moment SignalWire transcribes both legs and POSTs each result to
`/transcript` on this app. The app stores every event per call in
`data/runtime/transcripts/<call_id>.jsonl`, serves the merged transcript at
`/calls/<call_id>`, and re-broadcasts each segment over Server-Sent Events at
`/events`. By default the line is a dictation line that stays open for ten
minutes. Set `MEETING_BRIDGE_NUMBER` to connect the caller to a second party
instead, and both sides are transcribed.

## How it works

With `SIGNALWIRE_SIGNING_KEY` set, `POST /transcript` also needs a valid
`X-SignalWire-Signature`. Each SSE subscriber has a bounded queue, and one that
falls `SSE_QUEUE_MAX` segments behind is disconnected. All knowledge of the
event payload lives in one function, `parse_event()` in `adapter.py`, and
every raw body is kept next to the parsed segments. The docs do not publish
the webhook body; the adapter is written against bodies the author captured
from a live call. Each utterance arrives as one final result carrying
`call_info.call_id`, `channel_data.call_answer_date` and an `utterance` with
`role`, `content`, a microsecond `timestamp`, `utterance_id` and `confidence`.
At hangup one `transcribe.conversation_log` body repeats the whole
conversation and is stored raw. The `play` greeting is transcribed too, as
`local-caller`.

Where each mechanism lives in the repository:

- `SWMLService` and `add_verb`, with no `ai` verb: `app.py`, `build_swml()`
- `live_transcribe` `start` with `webhook` and `live_events`: `build_swml()`
- `connect` to a second party, optional: `build_swml()`
- the payload adapter, the one place that knows the event shape: `adapter.py`, `parse_event()`
- the partial/final merge, per-call store and SSE fan-out: `consumer.py`, `merge()`, `TranscriptStore`, `Broker`
- platform versus viewer login, and the webhook signature: `consumer.py`, `create_router()`; `app.py`, `auth_checkers()`, `signature_verifier()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and captured fixtures. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

The store writes to local disk and SSE needs a long-lived connection, so it is
not suited to serverless; swap `TranscriptStore` for a database first. Three
things are open upstream. With `live_events: true` the live call delivered
only final utterances, so the partial-merge path is tested from a synthetic
fixture. No source documents `live_transcribe` on a leg inside
`join_conference`, so this is a single-call dial-in. And whether these
webhooks carry `X-SignalWire-Signature` is unconfirmed, so leave the signing
key blank until a live call shows signed events, or every event gets a 403.
The recipe `transcribe-a-call-in-the-background` is the verified 3.0.1 version
of the verb.

## What to change first

Open `config.py`: `TRANSCRIPT_DIR` and the `TranscriptStore` class it feeds
decide where transcripts are delivered (file, database or queue). Then set
`GREETING`, `LANGUAGE_CODE` and `MAX_CALL_SECONDS`, and `MEETING_BRIDGE_NUMBER`
in `.env` if the line should connect to a second party.
