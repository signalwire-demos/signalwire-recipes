# AI restaurant reservation line: a booking the model cannot confirm until code has made it

> A restaurant reservation demo built to show a voice AI agent that cannot announce a booking the code has not made. One step exposes one tool, the handler checks hours and party size, writes the row, and only then moves the call on.

**Scenario:** A caller books a table by phone and hears a confirmation code read back from the row the handler wrote

## What this demonstrates

The model cannot confirm a booking the code has not made. The `take_booking`
step exposes one tool, `book_table`, and declares `valid_steps=[]`, so the
model has no `next_step` tool and cannot leave the step on its own. The handler
checks the opening hours and the party size in Python, appends the row to the
reservation file, and only then calls `swml_change_step("confirmed")`. A
rejected request returns no action, so the call stays where it was. The
`confirmed` step has no tools and reads the booking back from `global_data`,
which the handler wrote. Nothing the model said is read back.

The agent answers for the restaurant and asks for a name, party size, date,
time and a callback number. It books the table, or explains why it cannot
(closed that day, outside seating hours, party too large) and asks for
something that works. Once the booking is saved it reads the details and a
confirmation code back.

## How it works

Two steps in one `AgentBase`. A dynamic config callback runs on every request
and puts today's date and weekday into `global_data`. The model can then turn
"Friday" into a date without guessing the year. `check_request()` holds the
rules: a party size within `MAX_PARTY`, a date inside `BOOKING_WINDOW_DAYS`,
and a time between opening and the last seating. Each refusal is a sentence
the model relays, and the handler writes nothing until every check passes.

Where each mechanism lives in the repository:

- `define_contexts` and `add_step`: `app.py`, `ReservationAgent.__init__`
- `set_functions(["book_table"])` and `set_valid_steps([])`: the `take_booking` step
- `set_functions([])`, `set_valid_steps([])` and `set_end(True)`: the `confirmed` step
- `update_global_data` then `swml_change_step`: the `book_table` handler
- `set_dynamic_config_callback`: `add_today`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock data under `data/`. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The reservation sink is a local JSON file, so the app is not suited to
serverless as shipped. Point `save_booking()` at a database or your booking
system first; `agent.run()` then detects AWS Lambda and Google Cloud Functions
unchanged.

## What to change first

Open `config.py`: set `RESTAURANT_NAME`, `OPENING_HOURS`, `LAST_SEATING_MINUTES`
and `MAX_PARTY`. `RESERVATIONS_FILE` is the sink. To write to a real booking
system, replace `save_booking()` in `app.py`.
