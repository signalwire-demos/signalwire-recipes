# Live captions from a phone call: a web page that shows each line with its real delay

> A live captions demo built to show a transcript stream rendered in a browser with its latency measured. The delay is computed on the server from the platform's timestamp, and the page can read one call but change nothing.

**Scenario:** Open a web page while a call is running and watch captions appear, partial text in grey and finals solid, each with its measured delay

## What this demonstrates

The display shows its own latency, and it cannot change what was said. Each
segment's `delay_ms` is computed on the server: the platform's event time
against the moment the consumer received the webhook. The browser's clock is
never used, so a slow laptop cannot hide a slow pipeline. The page is
read-only, and so is its login. The SWML basic auth is the platform's and
alone can POST `/transcript` or list every call. The viewer login opens
`/captions` and reads one call it names, and anything else gets a 403. The
call flow underneath is code: `live_transcribe` starts right after `answer`,
the webhook is your own endpoint, and the SWML has no `ai` verb.

A caller dials the number and hears one sentence saying the call is
captioned. SignalWire transcribes both legs and POSTs each result to this
app, which stores it and pushes it over Server-Sent Events. Open
`/captions?call_id=<id>` in a browser and log in with the viewer credentials.
The page draws partial text in grey italics and swaps it for solid text when
the final result arrives. The measured delay sits next to every line. The
transcript pipeline is the transcription line above, copied in so this folder
stands alone.

## How it works

The adapter reads the payload the author captured from a live call. Each
final utterance carries `utterance.timestamp` in microseconds, and the
measured delay on that call was 80 to 300 ms. A subscriber that falls
`SSE_QUEUE_MAX` segments behind is disconnected, and the page reconnects and
gets the replay. The delay is only as good as the clock sync between
SignalWire and your server, so run NTP.

Where each mechanism lives in the repository:

- `SWMLService` and `live_transcribe` with `webhook` and `live_events`: `app.py`, `build_swml()`
- the payload adapter: `adapter.py`, `parse_event()`
- the server-side delay, `ts` against `received_at`: `adapter.py`, `Segment.delay_ms`
- SSE fan-out with replay on connect: `consumer.py`, `Broker`, `GET /events`
- the captions page (partial grey, final solid, delay badge): `static/captions.html`, served at `GET /captions`
- platform versus viewer login, and the webhook signature: `consumer.py`, `create_router()`; `app.py`, `auth_checkers()`, `signature_verifier()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a static captions page. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

SSE needs a long-lived connection and the store writes to local disk, so
serverless is not a fit. A proxy in front must not buffer `/events`; the app
sends `X-Accel-Buffering: no` for nginx. Open upstream: the live call delivered
only final utterances, even with `live_events: true`. On a real call today
every line appears solid, and the grey partial path runs only from a synthetic
fixture. Conference behaviour is undocumented, so this is a single-call
dial-in. Whether the webhooks are signed is unconfirmed; leave
`SIGNALWIRE_SIGNING_KEY` blank until a live call shows signed events.

## What to change first

Open `config.py`. `SPEAKER_LABELS` decides which legs are shown and what they
are called; set a leg to `None` to hide it. `DELAY_SLOW_MS` and
`DELAY_LATE_MS` set when the delay badge turns amber and red. For the look,
edit the `<style>` block in `static/captions.html`.
