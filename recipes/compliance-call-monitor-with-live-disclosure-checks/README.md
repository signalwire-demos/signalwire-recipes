# Compliance call monitor: required disclosures checked as they are spoken, with one alert per miss

> A compliance monitor demo built to show rules enforced by code on a live transcript, not judged by a model. Each phrase counts by the time it was spoken, each rule settles once, and the alert goes by SMS or webhook.

**Scenario:** While a rep is on a live call, a rule engine checks each required phrase against its deadline and pages a supervisor once when one is missed

## What this demonstrates

Compliance is enforced by code, not judged by a model. The rules are plain
phrase matches on final transcript segments in `rules.py`. A phrase counts by
the time it was spoken, the segment's `ts`, not by when its webhook arrived.
Each call's clock starts when the platform answered it,
`channel_data.call_answer_date`, carried in every transcript event. Deadlines
are checked on a ticker, so a rep who says nothing still triggers the alert.
Each (call, rule) pair settles once, so the supervisor is never paged twice.
The SWML has no `ai` verb, and the transcript goes only to your own
authenticated webhook.

A call comes in on the monitored number and is connected to your rep, or held
open as a single-party line for testing. SignalWire transcribes both legs live
and POSTs each result to this app. A rule engine checks that each required
phrase in `config.RULES` was said within its deadline, for example "this call
is recorded" within 30 seconds. If the deadline passes without the phrase, the
supervisor gets exactly one alert, by SMS or by webhook. A late disclosure is
recorded but never sends a second alert, and `GET /calls/<call_id>/compliance`
shows each rule as `pending`, `passed`, `missed` or `late`.

## How it works

`live_transcribe` starts right after `answer` and before `connect`, so the
whole disclosure window is transcribed. The transcript pipeline is the
transcription line above, copied in so this folder stands alone, and every
segment passes through `MonitoredBroker.publish` into the rules. Audio played
by the SWML is transcribed too, as `local-caller`, so a disclosure you play
with `play` passes the rule on its own. That is the strongest form, because no
rep can forget it. Alerts go out through `client.messages.create` or a webhook
such as a Slack incoming webhook, chosen by `ALERT_TARGET`.

Where each mechanism lives in the repository:

- `SWMLService` and `live_transcribe` before `connect`: `app.py`, `build_swml()`
- the call clock from the platform's answer time: `adapter.py` (`answered_at`), `rules.py` (`observe`)
- every segment to the rules: `app.py`, `MonitoredBroker.publish`
- deterministic rules, exactly-once settle, grace period: `rules.py`, `ComplianceMonitor`
- the deadline ticker: `app.py`, `create_app()` lifespan
- the SMS alert (`client.messages.create`) or webhook: `alerts.py`, `AlertSender.send`
- the payload adapter: `adapter.py`, `parse_event()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and captured fixtures. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

Rule state is in memory and the deadline ticker needs a long-running process,
so run one instance and do not run it serverless. SMS alerts need a sender on
an approved 10DLC campaign, or use the webhook. Open upstream: only final
utterances arrived on the live call, and conference behaviour is undocumented,
so this is a single-call line. The rules use finals only, so the first point
does not change the results. Whether a rule set satisfies a regulation is for
your counsel; this code shows the enforcement.

## What to change first

Open `config.py`: `RULES` holds the required phrases, the deadline for each
(`within_seconds`) and which leg must say them. `ALERT_GRACE_SECONDS` sets how
long to wait for in-flight transcript events before declaring a miss. Set
`ALERT_TARGET` in `.env` to choose who is alerted and how.
