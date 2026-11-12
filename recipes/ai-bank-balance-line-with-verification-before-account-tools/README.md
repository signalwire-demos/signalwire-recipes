# AI bank balance line: account tools that do not exist until a handler verifies the caller

> A bank balance demo built to show a voice AI agent whose account tools appear only after a handler verifies the caller. Failures are counted on the server across calls, so a redial does not reset them.

**Scenario:** A caller proves who they are, then checks a balance, hears transactions or disputes a charge; three failures lock the account out

## What this demonstrates

The account tools do not exist in the model's world until a handler unlocks
them. The `verify_identity` step exposes one tool and declares
`valid_steps=[]`, so the model has no `next_step` tool and no account tools to
call, whatever the caller says. Only the `verify_identity` handler can open
`account_menu`: on a match it writes the customer into `global_data` and runs
`swml_change_step("account_menu")`. The failure count lives on the server in
`lockout.py`, not in `global_data`. Tool requests carry their own `global_data`
and `call_id`, so a request-side counter would reset on a redial and could be
forged.

The agent asks for an account number and date of birth and checks them against
a mock core banking system in `data/accounts.json`. Once verified, the caller
can hear the balance, list recent transactions, and open a dispute on one of
them. After three failed attempts the agent stops asking, says it could not
verify them, and either transfers to a specialist or ends the call.

## How it works

Failures count per account number, per caller ID and per call, across calls.
The third failure jumps to `escalate`. That account or phone then stays locked
out for `VERIFY_LOCKOUT_SECS` (15 minutes by default) after the last failure,
even with the right details. As a second line of defence, every account
handler re-checks verification against the server's record for this
`call_id`, never against `global_data.verified`. The `escalate_call` handler
returns `connect()` to `ESCALATION_NUMBER` when one is set, and `hangup()`
otherwise.

Where each mechanism lives in the repository:

- `set_functions(["verify_identity"])` and `set_valid_steps([])`: `app.py`, step `verify_identity`
- `update_global_data` then `swml_change_step("account_menu")`: the `verify_identity` handler
- `swml_change_step("escalate")` on the third failure: the same handler
- `${global_data.customer.name}` in step text: step `account_menu`
- `connect()` or `hangup()`: the `escalate_call` handler
- the server-side failure count and lockout: `lockout.py`
- the mock identity check: `crm.py`, `verify()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock data under `data/`. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The failure counts and verified calls are in-process memory, and
`open_dispute` appends to a local file. Move all three to shared storage
(Redis, your database) before deploying to Lambda, Cloud Functions or several
replicas. Otherwise each instance counts and verifies on its own.

## What to change first

Open `config.py`: set `BANK_NAME`, `MAX_VERIFY_ATTEMPTS`, `VERIFY_LOCKOUT_SECS`
and `ESCALATION_NUMBER`. Then replace `crm.verify()` in `crm.py` with a call to
your identity provider, and `crm.get()` with your core banking lookup. The step
machine in `app.py` stays the same.
