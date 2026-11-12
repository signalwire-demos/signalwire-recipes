# AI collections agent: a payment policy the model cannot reveal or bargain over

> A collections demo built to show a voice AI agent negotiating against a policy it has never seen. Minimum payment, maximum term and refusal limit live in code, and the handler moves the call when they are exhausted.

**Scenario:** A caller with an overdue balance proposes a plan, the policy accepts or refuses it, and repeated refusals end in hardship options

## What this demonstrates

A business outcome overrides whatever the model or the caller wants next.
`propose_plan` sends the caller's offer to `policy.py`, which checks the
minimum payment, maximum term and refusal count from `config.py`. Those numbers
appear nowhere in the prompt, step text, tool schemas or `global_data`, so the
model cannot reveal or bargain over a floor it has never seen. On the Nth
refusal the handler runs `swml_change_step("hardship_options")`, whatever
arguments the model sent, and every step has `valid_steps=[]`, so the model
cannot navigate back to `negotiate`.

The caller gives the reference number from their letter and their ZIP code.
The agent finds the account in a mock ledger, states the balance, and asks what
the caller can pay each month and for how long. A plan the policy accepts is
recorded and read back; a plan it refuses gets a polite no and a nudge in the
right direction. After enough refusals the agent offers hardship options
instead, and a caller who asks for a person is handed to a human.

## How it works

The account and the refusal count live on the server, keyed by `call_id` in
`lockout.py`. `find_account` opens that record and every later tool reads only
it, never request `global_data`, which a forged tool request could fill in.
`global_data` gets a copy for the prompt text only. A match on `find_account`
discloses who owes what to whom, which must not reach a third party. Nothing
about the account is spoken before it, and guessing is limited. Failed lookups
count on the server per reference number, caller ID and call, across calls.
After `MAX_LOOKUP_FAILURES` that reference or phone gets no match for
`LOOKUP_LOCKOUT_SECS`, even with the right ZIP code.

Where each mechanism lives in the repository:

- the thresholds, read only server side: `config.py` for the values, `policy.py` for `evaluate` and `refusals_exhausted`
- `swml_change_step("hardship_options")` on the Nth refusal: `app.py`, `to_hardship()`, called from `propose_plan` and `decline_plan`
- refusal wording that hides the numbers: `app.py`, `REFUSAL_HINTS`
- `set_functions` and `set_valid_steps([])` on every step: `CollectionsAgent.__init__`
- `swml_change_step("escalate")`, then `connect()` or `hangup()`: the `escalate` and `transfer_to_agent` handlers
- the lookup failure count and lockout: `lockout.py`, used by `find_account`
- the outcome log: `ledger.py`, `record()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock ledger under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

`ledger.record()` appends to a local file, and the open accounts, refusal
counts and lookup failures are in-process memory. Point `OUTCOMES_FILE` and
the lockout at shared storage before deploying to Lambda, Cloud Functions or
more than one replica. The policy is a demonstration of the pattern; what a
collections call may say is a matter for your counsel, not this code.

## What to change first

Open `config.py`: set the policy thresholds (`MIN_MONTHLY_PAYMENT`,
`MAX_TERM_MONTHS`, `MAX_REFUSALS`) and the `HARDSHIP_OFFERS` your business can
make. Keep numbers out of the offer text, since that text goes into the prompt.
Then replace `ledger.find()` with your collections system.
`MAX_LOOKUP_FAILURES` and `LOOKUP_LOCKOUT_SECS` set the lookup lockout.
