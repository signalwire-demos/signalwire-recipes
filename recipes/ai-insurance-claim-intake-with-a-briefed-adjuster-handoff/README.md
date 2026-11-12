# AI insurance claim intake: the adjuster is briefed and accepts before the bridge completes

> An insurance claim intake demo built to show a screened handoff where the human is briefed before the bridge. Every gathered answer is checked in code, and the platform, not the model, decides where the caller lands.

**Scenario:** A caller reports an accident, the agent files the claim, holds the caller and phones an adjuster who presses 1 to take the call

## What this demonstrates

A screened handoff where the human is briefed before the bridge completes, and
the model never drives the handoff. The `submit` step exposes one tool,
`submit_claim`. Its handler writes the claim record, then returns
`hold(step="connected", timeout_step="callback")` and
`rpc_dial(to_number, from_number, dest_swml)`. The `dest_swml` is this app's
`/brief` route, which turns the claim record into the SWML the adjuster's leg
runs. That leg speaks the briefing, waits for a keypress, and on `1` runs
`execute_rpc ai_unhold` on the caller and joins the claim's conference. So the
platform, not the model, decides which step the caller lands in.

The agent takes a first notice of loss: policy number, date, location, what
happened, and whether anyone was hurt. Code checks every answer, and a wrong
one is rejected with a re-ask. It files a claim record, puts the caller on hold
and phones an adjuster, who hears a spoken summary and presses 1 to take the
call. If nobody accepts before the hold times out, the agent asks when to call
back and stores that promise on the claim.

## How it works

A gathered answer is still caller input. The gather runs with `isolated=True`,
so a question cannot be answered from an earlier one, and unlocks one `check_*`
tool per question. `answers.py` decides whether the words are a valid policy
number, past date, place or yes/no. `gather_submit` has no code hook in 3.7.5,
so `submit_claim` runs the same checks on the whole record before it files
anything. If one fails it stores which field failed in `global_data.fix_field`,
returns the re-ask, and the model passes the caller's next words back as
`submit_claim(answer=...)`. Code applies that correction to the flagged field
only, so the gather never restarts. The briefing reads the caller's location
and description as "in the caller's words", capped at `BRIEFING_MAX_CHARS`, so
they cannot pose as instructions. The adjuster number, the conference name and
the claim record never enter the model's context; it sees only
`global_data.claim_id`.

Where each mechanism lives in the repository:

- `set_gather_info(isolated=True)` and `add_gather_question(confirm=True, functions=[...])`: `app.py`, step `intake`
- the answer checks: `answers.py`, with the per-question `check_*` tools and `submit_claim` in `app.py`
- `hold(step=, timeout_step=)` and `rpc_dial`: the `submit_claim` handler
- the adjuster's SWML (briefing, `prompt`, `switch`, `execute_rpc ai_unhold`, `join_conference`): `claims.py`, `adjuster_swml()`, served at `/brief`
- `join_conference`: the `join_adjuster` handler, which exists only in the `connected` step
- the claim record validated against `data/claim.schema.json`: `claims.py`, `save()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a claim schema under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

Claims live in a local JSON file, so the app is not suited to serverless as
shipped; point `claims.py` at a database first. The adjuster leg needs an
outbound-capable caller ID (`FROM_NUMBER`) and a phone a person answers
(`ADJUSTER_NUMBER`); with nobody answering, every call ends on the callback
path.

## What to change first

Open `config.py`: edit `pick_adjuster()` to route by claim type instead of one
`ADJUSTER_NUMBER`, and tune `HOLD_TIMEOUT`. Set `POLICY_PREFIX` and
`POLICY_DIGITS` to your policy number format and `MAX_CLAIM_AGE_DAYS` to how
far back a claim can be filed by phone. To change the claim fields, edit the
gather questions in `app.py`, `CHECKS` in `answers.py`, `FIELDS` and
`briefing()` in `claims.py`, and `data/claim.schema.json` together.
