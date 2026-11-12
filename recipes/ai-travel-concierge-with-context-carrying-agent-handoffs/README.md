# AI travel concierge: two agents handing a caller back and forth with context and no transcript

> A travel concierge demo built to show two voice AI agents trading a caller with context in both directions. A one-time token in the transfer URL keys a short-lived record, and each agent rebuilds its state from that.

**Scenario:** A caller plans a trip with a concierge, is handed to a booking desk that already knows the trip, and comes back with the hold made

## What this demonstrates

The handoff carries context, but no transcript, in both directions.
`handoff_to_booking` validates the trip: a known destination, 1 to
`MAX_TRAVELERS`, a real month name. It writes the summary from those fields
and saves `{summary, trip, looked_up, call_id}` to a short-lived store with a
30-minute TTL. Only an opaque one-time token goes into the transfer URL,
`/booking?h=<token>`. The booking agent's dynamic config callback claims the
record, read once and then deleted, and rebuilds `global_data` from it. The
booking tools take no destination or party-size arguments; they read them from
`global_data.trip`, so the model cannot book a different trip.

Two agents run on one server. The concierge at `/concierge` answers questions
about the destinations in `data/destinations.json`. When the caller wants to
book, it confirms the destination, travellers and month and transfers to the
booking desk at `/booking`. The booking desk greets the caller with the trip
already known, reads flights with enough seats, and holds the one the caller
picks. Then it hands the caller back to the concierge, who already knows what
was held.

## How it works

The options are spoken by the platform, not paraphrased by the model.
`from_handoff` numbers the matching flights before the AI starts and sets them
as the booking agent's `static_greeting`. `search_flights` stores them in
`global_data.options` and returns "Option 1: departing ..." lines with no
flight IDs. `hold_flight` takes an option number, and code maps it to the
stored flight, re-checked against inventory; any other number is refused. The
booking agent sets `swaig_post_conversation`, and `return_to_concierge`
refuses to hand back until the log shows the caller has spoken since the hold.
The way back is the same shape: a new record with a fresh token and the
booking result inside it, then a transfer to `/concierge?h=<token>`. There
`from_booking` claims it and writes a "Returning caller" prompt section in
code.

Both transfers are `swml_transfer(..., final=True)`: each agent's AI session
ends and the other agent's SWML takes the call. On the author's test calls the
platform rejected a non-final transfer to a second AI agent with a 409 "Wait
for ai to finish". That is why the return trip is an explicit transfer written
by the handler.

Where each mechanism lives in the repository:

- `AgentServer` with two agents: `app.py`, `/concierge` and `/booking`
- `swml_transfer(dest, ai_response, final=True)`, both ways: `handoff_to_booking` and `return_to_concierge`
- the handler-written handoff record and one-time token: `handoff.py`, `save` and `claim`
- `set_dynamic_config_callback` rebuilding context: `BookingDesk.from_handoff`, `ConciergeDesk.from_booking`
- tools that read the trip from `global_data`, not arguments: `search_flights` and `hold_flight`
- `static_greeting` set per call, `FunctionResult.say()` for the options: `from_handoff`, `search_flights`, `hold_flight`
- `swaig_post_conversation` and the hand-back gate: `caller_spoke_after`, `return_to_concierge`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock inventory under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

The handoff store is a local JSON file, so both routes must share a disk. Move
`handoff.py` to Redis or a database, keeping the TTL, before running more than
one instance or on Lambda. The booking agent runs on `gpt-4.1-mini` because the
default model read back flights that did not exist on the author's test calls.
Whether `swml_transfer(final=False)` is meant to support a second AI agent as
the target is a question for the platform team.

## What to change first

Open `config.py`: set `AGENCY_NAME`, the two voices, `BOOKING_MODEL`,
`MAX_TRAVELERS`, and point `DESTINATIONS_FILE` at your inventory.
`HANDOFF_FILE` and `HANDOFF_TTL_SECS` control the store. To add another
specialist (hotels, cars), copy `BookingDesk`, give it its own route and tools,
and register it with `server.register(...)`.
