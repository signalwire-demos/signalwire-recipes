# After-hours AI answering service: code decides whether the AI is on the call at all

> An answering service demo built to show a per-call check deciding whether an AI answers at all. In hours the SWML is a plain connect, after hours one tool classifies urgency and the handler picks the route.

**Scenario:** During business hours calls ring the office with no AI; after hours an agent takes a message by text or forwards an urgent call

## What this demonstrates

Code decides whether the AI is on the call at all. A dynamic config callback,
`per_call`, runs on every call and checks the clock against `TZ`, `HOURS` and
`data/holidays.json`. During hours it renders SWML that is a `connect` and a
`hangup`, with no `ai` verb. After hours the AI has one tool, `submit_call`.
Its handler applies the urgency rule, a whole-word keyword list in
`config.py`, and either connects to the on-call line (`forward_urgent`) or
sends the SMS (`take_message`). The model cannot choose a route, because there
is no connect, forward or SMS tool for it to call.

If the office is open, the call rings the office line and no AI is involved.
If it is closed, the agent says so and asks for the caller's name, callback
number and what the call is about. A routine call is texted to the owner, and
the caller hears that someone will call back. An urgent one is connected to
the on-call technician right away.

## How it works

Before texting, `take_message` checks the callback number is a real phone
number, normalised to E.164. It sends at most one owner text per caller ID
every `SMS_THROTTLE_MINUTES`, so repeat calls cannot flood the owner. The clock
is injected (`AnsweringService(clock=...)`), so the tests pin it to a weekday,
a night, a Sunday and a holiday and assert which document each gets.

Where each mechanism lives in the repository:

- `set_dynamic_config_callback`, with `render_document` returning the office SWML: `app.py`, `per_call`
- SWML `connect` with no `ai` verb: `app.py`, `office_swml`
- `set_functions` and `set_valid_steps([])`: steps `intake` and `wrap_up`
- `FunctionResult.connect`: `forward_urgent`
- `FunctionResult.send_sms` then `swml_change_step`: `take_message`
- the urgency rule: `is_urgent`, keywords in `config.URGENT_KEYWORDS`
- the callback number check and per-caller SMS throttle: `phone_number` and `sms_allowed`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a holiday file under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

Its author marks it `proposed`: built, with its live test still to come.

The agent keeps no local state, since the clock check runs per request, so
`agent.run()` works unchanged on AWS Lambda or Google Cloud Functions. `tzdata`
is pinned so the time zone resolves in slim images. The owner text needs an
SMS sender registered for 10DLC or verified toll-free; an unregistered
number's texts are rejected by the carriers.

## What to change first

Open `config.py`: set `BUSINESS_NAME`, the `TZ` and `HOURS` defaults, and
`URGENT_KEYWORDS`. Put your closed dates in `data/holidays.json`. For a smarter
rule (VIP callers, an on-call rota), replace `is_urgent` in `app.py`; it is
the only thing that picks the route.
