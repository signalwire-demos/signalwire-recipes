# Support copilot that acts: a sidecar issues the credit the rep offers, under a cap enforced in code

> A support copilot demo built to show an ai_sidecar executing scoped tools on a call it does not own. The cap, the caller binding and the one-credit-per-order rule live in the handler, and every refusal reads the same to the model.

**Scenario:** A customer talks to a human rep while a sidecar looks up the order and issues the credit the rep promised, or refuses and says why on the rep's screen

## What this demonstrates

Scoped tool execution mid-call, without the AI owning the call. The SWML is
`answer`, `ai_sidecar`, `connect`, `hangup`; there is no `ai` verb, so two
people talk while the sidecar acts. Its model has exactly two tools,
`lookup_order` and `issue_credit`. The credit rules live in the `issue_credit`
handler, not the prompt. The handler enforces the cap (`config.CREDIT_CAP_USD`)
and allows one credit per order. It refuses an unknown order, a zero or
negative amount, more than the order total, or an amount that is not a finite
number. Words do not move money: the order's phone must match the caller's
number, which `on_request()` takes from the platform's SWML request
(`call.from`) and keeps by `call_id`.

A customer calls the support line. SignalWire attaches an `ai_sidecar` to the
call and bridges the customer to the rep's phone. When an order number comes
up, the sidecar looks it up and the rep's web page shows the full record. When
the rep says "I'll put a ten-dollar credit on that", the sidecar issues the
credit mid-call. It does so only on an order that belongs to the number the
customer is calling from. The rep page shows whether it was issued, or refused
and why.

## How it works

The cap never appears in the prompt, a tool description or a tool response.
Every refusal returns the same sentence, so the model cannot probe for the
limit; the rep's card gets the real reason. A write takes the order ID
exactly, and only `lookup_order` resolves a misheard number. Speech-to-text
once wrote an order number as spoken digits, and `resolve_order_id()` maps
those to the one order whose number ends in them. The check and the ledger
write run under one lock. `lookup_order` gives the model status, items and
total; the customer's phone and the account notes go only to the rep's screen.
The tools are `secure=False` because sidecar tool calls carry no per-call
SWAIG token, so `/swaig` is guarded by the platform's basic auth alone. Reps
log in to `/rep/` with a separate `REP_USER` and `REP_PASSWORD` that `/swaig`,
`/events` and `/` refuse.

Where each mechanism lives in the repository:

- `SWMLService` hosting `ai_sidecar`, schema-validated by `add_verb`: `app.py`, `SupportCopilot.__init__`, `sidecar_config()`
- `SWAIG.functions` set to exactly `[lookup_order, issue_credit]`: the `define_tool` calls and `sidecar_config()`
- the cap enforced in the handler and never shown to the model: `credit_refusal()`, `issue_credit()`, `REFUSED`
- the sidecar callback consumer: `on_event()` and `POST /events`
- the order ID as heard, resolved in code for lookups only: `orders.py`, `resolve_order_id()`
- the credit bound to the caller's number: `on_request()`, `caller_of()`, `credit_refusal()`
- the rep page over SSE with its own login: `GET /rep/stream`, `build_app()`, UI in `web/`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock order backend. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

Its author marks it `blocked`: it runs on the author's Space, and a platform
question it depends on is still open.

`ai_sidecar` worked on the author's Space; no public source says whether it is
generally available. The caller binding, the exact-ID credits and the rep
login were added after the author's live calls and are tested offline only.
They assume the sidecar's tool calls carry the same `call_id` as the SWML
request, with `caller_id_num` as a fallback. No `insight` card was seen live.
There is no documented way to whisper to the human rep and no documented
command to start a sidecar on a call in progress. Not built: an approve button
that makes the rep confirm each credit; add it before raising
`CREDIT_CAP_USD`. Run one long-lived container, since the rep page holds an
SSE connection, cards live in process memory, and the mock ledger is a local
file.

## What to change first

Open `config.py`. `CREDIT_CAP_USD` is the most the copilot can credit without
a supervisor. `ORDERS_FILE` and `CREDIT_LEDGER` point at the mock order
backend. To use your real order system, replace `load_orders()` and
`record_credit()` in `orders.py` with calls to your API, and keep the checks
in `credit_refusal()` in `app.py`.
