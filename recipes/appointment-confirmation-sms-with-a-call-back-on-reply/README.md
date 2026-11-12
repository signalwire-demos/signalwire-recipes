# Appointment confirmation by SMS: a text built by the handler and a reply that calls the customer back

> An appointment confirmation demo built to show one booking presented across voice and SMS with its memory in code. The handler writes the text from the stored record, and the dial-back loads that record before the model speaks.

**Scenario:** A caller books by phone, gets the details by text, and a reply of CHANGE places a call back that already knows the booking

## What this demonstrates

The same booking is presented across voice and SMS, and the memory lives in
code, not the model. The text is built by the handler from the stored record
through `config.SMS_TEMPLATE`. The model never writes the date, time or
confirmation number, and never picks the destination. The `to` number comes
from `global_data.caller`, which dynamic config set from the call itself. On
the dial-back, dynamic config (`preload`) reads `?booking=AC-1001`, loads that
record into `global_data` and sets `initial_step` to `reschedule`.
`reschedule_appointment` takes only a date and time; which booking it changes
comes from `global_data`, so the model cannot move someone else's appointment.

The agent asks for the caller's name and one of the open slots and saves the
booking. It texts the date, time and confirmation number from the SMS number.
If the customer later replies "change it" (or "reschedule", "move", "call"),
the `/sms` webhook finds their booking by phone number and places a REST call
back. That call opens on the reschedule step with the booking loaded, so the
agent greets them by name and asks only for the new slot. Any other reply gets
the booking details texted back.

## How it works

`book` and `reschedule` each expose one tool and `valid_steps=[]`. A new caller
has no way into `reschedule`, and only handlers reach `confirmed`, which has no
tools. The inbound text arrives as a cXML-style form POST, is checked with
`validate_webhook_signature`, and is answered with a cXML reply. A text from
the SMS number itself gets no reply, so the number cannot loop on its own
answers. A booking gets at most one call back every
`DIAL_BACK_COOLDOWN_MINUTES`, so a burst of CHANGE texts rings the phone once.

Where each mechanism lives in the repository:

- `define_contexts`, `set_functions` and `set_valid_steps([])`: `app.py`, `ConfirmationAgent.__init__`
- `send_sms`, `update_global_data` and `swml_change_step`: `app.py`, `confirm()`, used by both tools
- `set_dynamic_config_callback` and `set_initial_step`: `app.py`, `preload()`
- REST `calling.dial`: `app.py`, `dial_request()` and `dial_back()`
- inbound SMS (form POST, cXML reply): `app.py`, `sms_router()` and `handle_sms()`
- `validate_webhook_signature`, required: `app.py`, `sms_router()`
- the per-booking call-back cooldown: `app.py`, `handle_sms()`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a booking store under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

Its author marks it `proposed`: built, with its live test still to come.

The booking store is a local JSON file; swap `load_bookings()` and
`save_bookings()` for a database before running serverless. The cooldown is
in memory, per process. Texts deliver only from a number on a 10DLC campaign
or verified toll-free. On the author's live test a text from an unregistered
number came back `undelivered`, rejected by the receiving carrier. The call
back needs an outbound-capable number for caller ID.

## What to change first

Open `config.py`: edit `SMS_TEMPLATE` (keep `{date}`, `{time}` and
`{confirmation}`), `ESCALATE_WORDS` (which replies trigger the call back) and
`DIAL_BACK_COOLDOWN_MINUTES`. Then point `SLOTS_FILE` and `BOOKINGS_FILE` at
your own calendar, or replace the store functions at the top of `app.py`.
