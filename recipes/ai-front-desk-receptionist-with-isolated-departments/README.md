# AI front desk receptionist: departments as isolated personas that cannot use each other's tools

> A front desk demo built to show one voice AI agent with four personas that cannot reach each other's tools. Each department is an isolated context, the routing graph is code, and a refund needs a verified invoice.

**Scenario:** A caller reaches one front desk and is routed to sales, support or billing, each a different voice with its own tools

## What this demonstrates

Personas that structurally cannot use each other's tools. Each department in
`config.DEPARTMENTS` becomes an isolated context (`set_isolated(True)`) whose
step lists only that department's tools with `set_functions`. `issue_refund`
is registered on the agent, but it exists in no sales, support or front-desk
step, so no prompt can talk sales into a refund. `valid_contexts` is the
routing graph: the model's built-in `change_context` tool offers only the
routes listed for the current department.

Riley at the front desk asks what the caller needs and hands them to the right
department. Franklin in sales quotes plan prices, and Rachael in support checks
outages and opens tickets. Dwight in billing looks up an invoice and refunds it
up to a limit. Callers can move between departments only along the routes the
code allows, and each handoff wipes the previous department's conversation.

## How it works

Every step declares `set_functions` explicitly, because a step without it
inherits the previous context's tools. Each persona gets its own voice through
one `add_language("English-<persona>", ...)` call, and enter fillers cover
each handoff. The refund amount comes from the invoice record, never from the
model's arguments. Invoice numbers are sequential, so a number alone opens
nothing. `get_invoice` also needs the billing ZIP on the record, gives one
answer for a wrong number or a wrong ZIP, and stops after
`MAX_LOOKUP_FAILURES` misses on a call. A match is stored in
`global_data.billing_verified`, and `issue_refund` takes no arguments, so it
refunds only that invoice. The tests read the SWML dump and assert all of this.

Where each mechanism lives in the repository:

- `add_context(...).set_isolated(True)`: `app.py`, one per entry in `config.DEPARTMENTS`
- `set_functions(dept["tools"])`: the `main` step of every context; the front desk gets `[]`
- `set_valid_contexts(dept["routes"])` and `set_valid_steps([])`: every context and step
- `add_enter_filler` and `add_internal_filler("change_context", ...)`: each handoff
- the invoice and ZIP check, with the refund target in `global_data`: `get_invoice` and `issue_refund`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock data under `data/`. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The agent itself is stateless, but `open_ticket` and `issue_refund` append to
local files in `data/`. Point `TICKETS_FILE` and `REFUNDS_FILE` at real
systems before running it on Lambda or Cloud Functions.

## What to change first

Open `config.py` and edit `DEPARTMENTS`. Each entry sets a department's
context name, persona, voice, role text, the tools it owns and the departments
it may route to. Then set `BUSINESS_NAME`, `REFUND_LIMIT` and
`MAX_LOOKUP_FAILURES`, and swap the files in `data/` for your own systems,
keeping a second factor like the billing ZIP on each invoice record.
