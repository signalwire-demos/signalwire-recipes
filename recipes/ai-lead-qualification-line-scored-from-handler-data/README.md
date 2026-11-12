# AI lead qualification line: a lead scored from typed handler data, not the transcript

> A lead qualification demo built to show post-call extraction from data the handlers wrote. Four tools record typed values, and the disposition reads only those, so a caller saying "mark me hot" changes nothing.

**Scenario:** A prospect answers four questions in any order and a hot, warm or cold lead lands in the CRM after the call

## What this demonstrates

Post-call extraction from handler-written data, not from transcript parsing.
The four `record_*` handlers validate and write typed values into
`global_data`: `budget_usd` as an integer, `timeline_months` as an integer,
`is_decision_maker` as a boolean, `need` as an enum. `on_summary` builds the
CRM disposition from that `global_data` only; it never reads `call_log`,
`conversation_summary` or the model's post-prompt output. A caller who says
"mark me as hot" changes nothing, and the score is a plain Python rule you can
unit test.

The agent asks about budget, timeline, who signs off, and what the caller
needs, in whatever order the conversation goes. Each answer is recorded by a
tool as a typed value. Once all four are in, the agent thanks the caller and
says a specialist will follow up. When the call ends, the app scores the lead
hot, warm or cold and appends it to `data/leads.jsonl`. With the HubSpot sink
on, it creates a contact instead.

## How it works

The `qualify` step has the four tools and `valid_steps=[]`, so the model
cannot leave it. The handler that records the last missing field calls
`swml_change_step("wrap_up")`, and `wrap_up` has no tools. The upstream test is
the point of the recipe. It hands `on_summary` a payload whose transcript and
summary both say "hot lead" and fails on any read of those fields. The row has
to come out cold, scored from `global_data`.

Where each mechanism lives in the repository:

- `define_contexts`, `add_step`, `set_functions` and `set_valid_steps([])`: `app.py`, steps `qualify` and `wrap_up`
- `update_global_data` then `swml_change_step`: `app.py`, the `record()` helper every `record_*` handler uses
- `set_post_prompt` and `on_summary`: `LeadQualificationAgent.on_summary`
- the disposition, scoring rule and CRM sinks: `disposition.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a file sink under `data/`.
It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

The file sink writes inside the container, so mount `data/` as a volume or use
`CRM_SINK=hubspot` to keep leads. Serverless works with the HubSpot sink; the
file sink needs a persistent disk. The HubSpot path needs a private-app token
with the `crm.objects.contacts.write` scope and is off by default.

## What to change first

Open `config.py`: change `FIELDS` and `NEEDS` to your own qualification
questions, and edit `SCORE_RULES` and `TIERS` to set what counts as hot, warm
and cold. A new field needs a `record_*` tool in `app.py`. For a CRM other
than HubSpot, add a function to `SINKS` in `disposition.py` and select it with
`CRM_SINK`.
