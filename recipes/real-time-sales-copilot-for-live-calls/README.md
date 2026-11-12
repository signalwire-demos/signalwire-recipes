# Real-time sales copilot: a sidecar that rides a human call and surfaces objection playbooks on the rep's screen

> A sales copilot demo built to show an ai_sidecar listening to both legs of a human call without speaking. A code classifier decides the objection category, and the talk tracks go only to the rep's page, never into the prompt.

**Scenario:** A customer talks to a human rep; when they raise a pricing, timing, competitor or authority objection, a talk-track card appears within a turn

## What this demonstrates

The sidecar rides a call it does not own. The SWML is `answer`, `ai_sidecar`,
`connect`, `hangup`. There is no `ai` verb, so no agent runs the call; the two
people talk, and the sidecar listens to both legs
(`direction: [remote-caller, local-caller]`). Its model has one tool,
`flag_objection(customer_quote)`, which hands the customer's words to a
plain-code classifier. The classifier is a set of regexes from
`config.PLAYBOOK` and it runs first, so the model never decides the category.
The talk tracks go only to the rep's page. They are not in the prompt, not in
the tool description, and not in the tool's response, and tests assert all
three.

A customer calls the sales line. SignalWire attaches an `ai_sidecar` to the
call and bridges the customer to the rep's phone. When the customer pushes
back, a card with that objection's talk track appears on the rep's web page
within a turn. "It's too expensive", "we already use Globex" and "I'd have to
run it by my CFO" each have one. Between objections the sidecar can send one
line of advice, which shows up as a "Copilot" card.

## How it works

Sidecar callbacks arrive at `POST /events` and are unwrapped from
`sidecar_event`. Every `turn` event carries the customer's words as
`customer_text`, and `on_event()` runs the same classifier on them in code. An
objection the model does not flag still reaches the rep, and a card already
pushed by the tool is not repeated within `config.REPEAT_AFTER_S`. `insight`
and `final` events become cards on the same Server-Sent Events stream, and the
rep's words are never classified. The tool is `secure=False` because the
sidecar's tool calls carry no per-call SWAIG token, so `/swaig` is guarded by
the platform's basic auth alone. That credential stays on the server: reps log
in to `/rep/` with their own `REP_USER` and `REP_PASSWORD`, which `/swaig`,
`/events` and `/` refuse. The rep page stays locked while `REP_PASSWORD` is
blank or equal to the platform password.

Where each mechanism lives in the repository:

- `SWMLService` hosting `ai_sidecar`, schema-validated by `add_verb`: `app.py`, `SalesCopilot.__init__`, `sidecar_config()`
- `SWAIG.functions` set to exactly `[flag_objection]`: `sidecar_config()`
- the deterministic objection classifier: `classify()`, rules in `config.PLAYBOOK`
- the sidecar callback consumer (`sidecar_event.type`, `turn.customer_text`): `on_event()` and `POST /events`
- the rep page over SSE: `GET /rep/stream`, UI in `web/`
- the rep login, separate from the platform credential: `build_app()`; `REP_USER` and `REP_PASSWORD` in `config.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a rep page under `web/`. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `blocked`: it runs on the author's Space, and a platform
question it depends on is still open.

`ai_sidecar` worked end to end on the author's Space. No public source says
whether it is generally available, so ask SignalWire support whether it is
enabled on yours. Event types seen live were `start`, `turn`, `request`,
`tool_call`, `tool_result`, `skip`, `stop` and `final`; no `insight` arrived,
so the insight card is untested live. Two things are open. There is no
documented way to whisper audio to the human rep. `rpc_ai_message` reaches
only an AI agent, which is why the cards go to a web page. No documented REST
or Relay command starts a sidecar on a call already in progress, so it is
attached in the SWML before `connect`. The rep page holds a long-lived SSE
connection and the cards live in process memory, so run one long-lived
container. One rep login sees every call's cards. The recipe
`run-an-ai-sidecar-on-a-live-call` is the planned verified version of the
verb.

## What to change first

Open `config.py`. `PLAYBOOK` holds your objection categories: the regexes that
trigger each one and the talk track the rep sees. Put your competitors in
`COMPETITORS` (they also become speech hints), and set `REP_NUMBER` in `.env`
to your rep's phone. To hand cards to your CRM or contact-centre UI instead of
the bundled page, replace `Feed.push` in `app.py`.
