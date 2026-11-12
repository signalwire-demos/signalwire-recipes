# AI support line with callback: the issue survives the queue and the return call without the model carrying it

> A support line demo built to show a callback whose context lives in a store, not the model. The handler files the triage and the caller's real number, a worker dials back, and the return call opens already informed.

**Scenario:** A caller describes a problem, reaches a human now or is called back later by a worker that already knows the issue

## What this demonstrates

Context survives the queue and the return call without the model carrying it.
`triage` exposes one tool, `request_human`. Its handler stores the triage in
`global_data` and checks availability in code (`rota.py`), then either
connects to the human or moves the call to `offer_callback` with
`swml_change_step`. `schedule_callback` writes the callback record from the
caller's real number, taken from call data rather than a model argument, and
the triage the handler stored. The return call has exactly one tool,
`connect_human`, and the phone number never enters its context.

The agent asks what is wrong and boils it down to a one-line issue and a short
summary. If a specialist is free on the rota, the caller is transferred
straight away. If not, the agent offers a callback to the number they are
calling from, asks when suits them, and says goodbye. A worker process calls
the customer back. The return call opens with "I'm returning your call about
your router dropping wifi", confirms they still need help, and connects them
to a human.

## How it works

The worker REST-dials the customer into `/callback?id=CB-0001`. On that route
a dynamic config callback looks the record up and sets `global_data` before
the model says a word. Because the caller ID can be spoofed, the store only
queues numbers it is willing to dial (`store.dialable`). That means E.164 under
`CALLBACK_ALLOWED_PREFIXES`, with premium and Caribbean area codes refused and
anonymous or SIP callers turned down. Each number gets one pending callback,
the queue is capped at `MAX_PENDING_CALLBACKS`, and the worker checks the
number again before it dials. Writes take a file lock, so the app and the
worker never hand out the same id. Two agents share one port through
`AgentServer`: the triage agent at `/` and the callback agent at `/callback`.

Where each mechanism lives in the repository:

- `set_functions` and `set_valid_steps([])`: `app.py`, steps `triage`, `offer_callback`, `returning`
- the availability check in code: `rota.py`, `human_available()`
- `update_global_data` then `swml_change_step` or `connect`: the `request_human` handler
- `set_dynamic_config_callback`: `CallbackAgent.load_context`
- REST `client.calling.dial`: `callback_worker.py`, `sweep()`
- the toll-fraud guard (allowed prefixes, dedupe, queue cap): `store.py`, `dialable()` and `create()`, rechecked in `sweep()`
- `AgentServer` with two agents on one port: `app.py`, `/` and `/callback`

## Limitations

This is a clone-and-own application in another repository, not a snippet: two
Python processes with a compose file, pytest tests and a rota under `data/`.
It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

The callback queue is a local JSON file shared through a volume, and the
worker is a long-running loop. Neither suits serverless as shipped: move the
store to a database and run the sweep on a scheduler first. The human leg
needs an outbound-capable caller ID (`FROM_NUMBER`) and a phone a person
answers (`HUMAN_NUMBER`).

## What to change first

Open `config.py`: set `HUMAN_NUMBER` and `FROM_NUMBER`, and point the
availability check at your ACD or rota. `AVAILABILITY` and `ROTA_FILE` are the
knobs, and `rota.human_available()` is the function to replace. The worker
calls back every pending record on each sweep; to honour `preferred_time`,
filter by it in `store.pending()`.
