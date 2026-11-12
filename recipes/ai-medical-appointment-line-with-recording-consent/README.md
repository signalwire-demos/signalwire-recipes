# AI medical appointment line: recording that starts only in the handler that records consent

> A medical appointment demo built to show compliance as a state machine rather than a prompt. The consent step has one tool, recording starts in its handler on yes, and the audit record is built from handler data.

**Scenario:** A caller hears a disclosure, says yes or no, and either books an appointment on a recorded call or holds one unrecorded

## What this demonstrates

Compliance as a state machine rather than a promise. The `consent` step's text
carries the disclosure, its only tool is `record_consent`, and `valid_steps=[]`
gives the model no way out. The scheduling tools do not exist in that step.
Recording starts in exactly one place: the `record_consent` handler, on
`answer=yes`, before it moves the call to `schedule`. A refusal moves to
`schedule_limited`, where `book_slot` is not defined, and `book_slot` re-checks
`global_data.consent` itself as well.

The agent reads the recording disclosure from `config.py` word for word and
asks whether the caller agrees. On a yes, recording starts and the caller can
book any open slot. On a no, the call stays unrecorded and the caller can only
place a tentative hold, which the front desk confirms later. After the call,
one audit line lands in `data/audit.jsonl` with the consent answer, its time,
and the disclosure version the caller heard.

## How it works

`on_summary` builds the audit record from the `global_data` the handlers wrote,
not from the transcript or the model's summary, so the record says what the
code did. The disclosure text and its version number live in `config.py`.
Bumping `DISCLOSURE_VERSION` every time the wording changes is what lets each
audit row prove which version the caller heard. The schedule is a mock in
`data/slots.json`, and `find_slots`, `book_slot` and `hold_slot` are the three
handlers that read and write it.

Where each mechanism lives in the repository:

- `set_functions` and `set_valid_steps([])`: `app.py`, steps `consent`, `schedule`, `schedule_limited`, `wrap_up`
- the disclosure in step text: step `consent`, from `config.DISCLOSURE_TEXT`
- `record_call`, `update_global_data` and `swml_change_step`: the `record_consent` handler
- the handler-side consent check: the `book_slot` handler
- `set_post_prompt` and `on_summary`: the audit record from `global_data`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock schedule under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

The audit log and the taken-slot list are local state, so the app is not
suited to serverless as shipped. Point `AUDIT_FILE` at durable storage, or
replace `on_summary` with a write to your system of record, and move the
schedule to a real backend first. Whether a disclosure satisfies a
jurisdiction's consent rules is for your counsel; this code shows where the
gate goes.

## What to change first

Open `config.py`: set `CLINIC_NAME`, rewrite `DISCLOSURE_TEXT` with your
counsel's wording, and bump `DISCLOSURE_VERSION` each time it changes. Then
swap the scheduling backend: point `SLOTS_FILE` at your own data, or replace
`load_slots()` and the three slot handlers in `app.py` with calls to your
practice-management system.
