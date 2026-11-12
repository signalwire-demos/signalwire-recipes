# AI appointment reminder caller: consent, do-not-call and calling hours enforced before the dial

> An appointment reminder demo built to show outbound voice AI with consent handling in code. The dialer skips anyone without consent, on the do-not-call list or outside hours. The model learns the appointment only after identity is confirmed.

**Scenario:** A dialer calls each consenting contact in their own calling hours, confirms identity before any detail, and lets them confirm, move or cancel

## What this demonstrates

Outbound dialing with consent handling in code rather than in the prompt.
`dialer.py` skips anyone without `consent=yes`, anyone on `data/dnc.txt`, and
anyone outside `CALL_WINDOW` in the contact's own `timezone`; `--dry-run`
prints each decision. The SWML for a call carries only `appointment_id` and
`first_name` in `global_data`. The appointment itself is loaded by the
`confirm_identity` handler, and only when the person says they are the
contact. A wrong person gets a callback number and the handler hangs up, so
the model never held the details it could leak.

`dialer.py` reads `data/appointments.csv` and calls each eligible contact.
When someone answers, the agent asks for the contact by first name without
saying why it is calling. If it is them, it reminds them of the appointment,
and they can confirm, move it to another open slot, or cancel. The change lands
in `data/calendar.ics`. If they ask not to be called again, their number goes
on the do-not-call list and the call ends.

## How it works

The model cannot pick the appointment. The manage tools take no appointment
id; they act on the id the dialer put in the SWML URL (`?appt=A-0101`), read
back from `global_data`. Opt-out is enforced in code: `opt_out` writes the
do-not-call list the dialer checks before every dial, then ends the call. The
dial itself is one REST call, `client.calling.dial`, with the per-call URL.

Where each mechanism lives in the repository:

- REST `client.calling.dial`: `dialer.py`, `dial()`
- the consent, do-not-call and local calling-hours filter: `dialer.py`, `skip_reason()`
- `set_dynamic_config_callback`, the per-call `global_data`: `app.py`, `configure()`
- `set_functions` and `set_valid_steps([])`: steps `confirm_identity`, `manage`, `wrap_up`
- `update_global_data`, `swml_change_step` and `hangup`: the `confirm_identity` and manage handlers
- the calendar backend: `calendar_ics.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a dialer script. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the
recipes here are verified against. Its claims are proven by its own tests, not
by a verifier in this repository. The repository carries no licence file at
the time of writing, which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

Run `dialer.py` on a schedule during the hours you want reminders to go out;
it re-checks consent, the list and local time on every run. The calendar and
the do-not-call list are local files, so mount `data/` and do not run this
serverless as shipped. Two items are open upstream. A Google Calendar backend
is not built, and the app refuses `CALENDAR_BACKEND=google`. There is no
answering-machine detection, so a voicemail is treated like a wrong person,
which is safe but wastes the call. Whether these rules satisfy the calling
laws where you operate is for your counsel.

## What to change first

Open `config.py`: point `APPOINTMENTS_FILE`, `DNC_FILE` and `CALENDAR_FILE` at
your own sources, or replace `contacts.py` and `calendar_ics.py` with adapters
for your scheduling system, keeping their function names. Set `BUSINESS_NAME`
and `CALLBACK_NUMBER`, and check `CALL_WINDOW`, `OPEN_WEEKDAYS` and
`OPEN_HOURS` against your rules.
