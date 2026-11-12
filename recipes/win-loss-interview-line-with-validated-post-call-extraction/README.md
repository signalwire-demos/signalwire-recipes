# Win/loss interview line: post-call extraction validated against a schema you own

> A win/loss interview demo built to show post-call analysis on structured extraction rather than a summary. The post prompt and the validator are generated from one JSON Schema, and a record that fails it is flagged, never repaired.

**Scenario:** A prospect gives a short interview, the call becomes a JSON record validated against a schema, and a report rolls the records up

## What this demonstrates

A post-call analysis pipeline built on structured extraction you own, not a
summary you hope is right. The interviewer has no tools (`set_functions([])`
on every step), so it cannot write or look anything up. Extraction runs on
SignalWire's AI. The post prompt is generated from the same JSON Schema in
`extraction.py` that `on_summary` validates against, with the outcomes and
reason categories enumerated from `config.py`. A summary that is not JSON, has
an unknown outcome, an invented reason category or an extra field is stored
with `valid: false` and its errors. It is not repaired or guessed at.

A prospect who recently chose, or did not choose, Example CRM calls the
interview line. The agent asks four things, one at a time: did they buy, what
mattered most, which other vendors they looked at, and what concerns they had.
After the call, SignalWire's AI turns the conversation into a fixed JSON
record. `python analyze.py --since 7d` rolls those records up into a report.
It shows the win rate, top reasons won and lost, a head-to-head table per
competitor, and the most common objections.

## How it works

`set_post_prompt` carries the generated prompt and `set_post_prompt_llm_params`
pins the extraction model's settings. `on_summary` writes one line per call to
`data/runtime/calls.jsonl`, valid or flagged. `analyze.py` re-validates every
row, lists bad ones under "Flagged", and counts only valid ones. Validation
uses jsonschema-rs, which the SDK already depends on, so no outside LLM key or
library is involved.

Where each mechanism lives in the repository:

- `set_functions([])` and `set_valid_steps`: `app.py`, steps `interview` and `wrap_up`
- `set_post_prompt` and `set_post_prompt_llm_params`: `app.py`, built from `extraction.POST_PROMPT`
- `on_summary`: `WinLossAgent.on_summary`, which writes `data/runtime/calls.jsonl`
- JSON Schema validation: `extraction.py`, `parse()`
- the aggregation into markdown: `analyze.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a report script. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The agent itself is stateless, but `on_summary` appends to a local file; point
it at a database or object store before deploying serverless. Pulling
summaries over REST instead of the post-prompt webhook is open upstream,
because the 3.7.5 SDK has no wrapper for it. The recipe
`extract-structured-data-after-a-call` is the verified 3.0.1 version of the
post-prompt mechanism.

## What to change first

Open `config.py`: `OUTCOMES`, `REASONS` and `MAX_REASONS` define the extraction
schema. Both the post prompt and the validator are built from them, so a
change shows up in each. `COMPETITOR_ALIASES` maps what prospects say to the
names in the report. To add a report section, add a block to `report()` in
`analyze.py`.
