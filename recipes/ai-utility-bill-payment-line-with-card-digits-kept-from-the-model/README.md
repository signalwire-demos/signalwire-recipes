# AI utility bill payment line: card digits that never reach the model, the recording or the logs

> A utility bill payment demo built to show a voice AI agent handing the card entry to the SWML pay verb. Recording stops before the first digit, the amount comes from the billing record, and the model never hears the result.

**Scenario:** A caller verifies an account, hears the balance and pays by keypad while the recording is paused

## What this demonstrates

Card digits never reach the model, the recording or this app's logs.
`take_payment` has no parameters. Its handler reads the amount from the billing
record of the account this call verified, which `verify_account` recorded on
the server keyed by `call_id`. Whatever amount the model or caller says is
ignored, and so is request `global_data`, which a forged tool request could
otherwise fill in. The handler returns `stop_record_call()` and then a transfer
SWML that runs `pay` and transfers back to this agent at
`/?pay_ref=<one-time ref>`. So the recording is paused before the first digit,
and the AI is not listening while the caller types.

The agent asks for the account number and service ZIP code. Once they match,
recording starts and the agent reads the balance due. To pay, the call is
handed to the SWML `pay` verb, which prompts for the card by keypad. The digits
go straight to the payment connector, here a mock served by this app at
`/pay`. The call then returns to the agent, recording resumes, and the agent
says whether the payment went through.

## How it works

The model never hears the pay verb's result. `configure()` turns the one-time
`pay_ref` back into the account, records it on the server for the returning
call's `call_id`, and starts the returning call at `after_payment`. That step's
one tool, `resume_recording`, restarts the recording and says "went through"
only on server-side evidence. Either the mock connector approved a charge
carrying this call's `pay_ref`, or the platform's `status_url` reported
`payment-completed`. Anything else is reported as not paid. `pay` cannot run as
an in-AI action; the platform rejects it with 409 "Wait for ai to finish".
That is why the handler transfers out and back. Verification failures are
counted on the server per account, caller ID and call, with a lockout after
`MAX_VERIFY_FAILURES`. The mock connector logs only the transaction id, amount
and result, and a test asserts no card data appears in any log output.

Where each mechanism lives in the repository:

- `set_functions` and `set_valid_steps`: `app.py`, steps `verify`, `bill`, `after_payment`, `wrap_up`
- `record_call`, `update_global_data` and `swml_change_step`: the `verify_account` handler
- `stop_record_call`, then `execute_swml([pay, transfer], transfer=True)`: the `take_payment` handler
- `set_dynamic_config_callback` and `set_initial_step("after_payment")`: `configure()`
- `record_call` to resume, with the outcome from connector approvals: the `resume_recording` handler
- the payment connector and `status_url`: `connector.py`, `POST /pay` and `POST /pay/status`
- the server-side failure count and lockout: `lockout.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock payment connector. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

The `/pay/status` events, the connector's approvals, the pending references,
the verified calls and the failure counts are kept in memory per process. Move
them to a shared store before running more than one instance or on Lambda.
The platform's post-prompt payload carries `SWMLVars.pay_payment_results`,
which includes the masked card number, expiry and postal code. This app does
not log it; if you add an `on_summary`, drop that field before storing
anything. Payment isolation here is a pattern the code follows, not a
compliance certification.

## What to change first

Open `config.py`: set `PAY_CONNECTOR_URL` to your processor's connector, which
must speak the request and response contract described at the top of
`connector.py`, and set `UTILITY_NAME`. Point `ACCOUNTS_FILE` at your billing
system, or replace `load_accounts()` in `app.py`. `PAY_MAX_ATTEMPTS`,
`PAY_SECURITY_CODE`, `PAY_POSTAL_CODE` and `PAY_CARD_TYPES` tune the pay
prompts; `MAX_VERIFY_FAILURES` and `VERIFY_LOCKOUT_SECS` set the lockout.
