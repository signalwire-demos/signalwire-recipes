# AI order status line: the handler holds the full record and the model sees a curated slice

> An order status demo built to show verify-then-expand projection. The full record enters global_data, the step text exposes three fields, and the refund thresholds are read only inside the handler.

**Scenario:** A caller checks an order, asks for a refund, and a server-side rule credits it or hands it to a specialist, once per order

## What this demonstrates

The handler loads the full record, but the model sees only a curated slice.
`verify_identity` puts the whole order into `global_data`, including
`risk_flag`, `prior_refunds` and `internal_notes`. `global_data` is not part
of the model's context on its own; it reaches the model only through
`${global_data.*}` in step text. The `order_status` step text is built from
`config.CURATED_FIELDS` (status, ETA, items). The refund thresholds live in
`config.py` and are read only inside `request_refund`, which tells the model
the outcome and never the rule. The model cannot leak a flag it never saw, or
argue with a limit it does not know.

The caller gives an order number and the shipping ZIP code. Once those match
an order in the mock CRM, the agent can tell them the status, the estimated
delivery and what is in it. If the caller asks for a refund, a server-side
rule decides. Small orders on clean accounts get an automatic credit, and
everything else goes to a specialist. Each order is credited at most once, so
asking again on the same call or a later one does not pay out twice. Three
failed verifications also go to the specialist.

## How it works

A refund is handled once per call, since `request_refund` checks
`global_data.refund`, and `crm.issue_credit` dedupes by order id under a lock.
A repeat request or a later call gets the first reference back and no second
credit. The verification step has the same shape as the bank balance line,
copied rather than imported: one tool, `valid_steps=[]`, and the third failure
jumps to `escalate`.

Where each mechanism lives in the repository:

- the full record into `global_data`: `app.py`, the `verify_identity` handler
- the curated `${global_data.order.<field>}` slice: `app.py`, `curated_step_text()`, fields from `config.CURATED_FIELDS`
- the refund rule, server side only: `app.py`, `refund_decision()`, thresholds in `config.py`
- one credit per order (lock plus dedupe): `app.py`, `request_refund`; `crm.py`, `issue_credit()`
- `swml_change_step("escalate")`: the `request_refund` and `verify_identity` handlers
- `set_functions` and `set_valid_steps([])`: steps `verify_identity`, `wrap_up`, `escalate`
- `connect()` or `hangup()`: the `escalate_call` handler

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock CRM under `data/`.
It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

The order record travels in `global_data`, so the agent is stateless, but
`crm.issue_credit` appends to a local file and its once-per-order lock is per
process. Point `CREDITS_FILE` at real storage with a unique key on the order
id before deploying to Lambda or Cloud Functions. The recipe
`hide-fields-from-the-model` is the verified 3.0.1 version of the projection
idea.

## What to change first

Open `config.py`: `CURATED_FIELDS` is the slice of the order the model may see
(add or remove fields there, never `risk_flag`). Then set the refund rule
(`AUTO_CREDIT_LIMIT`, `MAX_PRIOR_REFUNDS`, `REFUNDABLE_STATUSES`) and replace
`crm.verify()` with your order system.
