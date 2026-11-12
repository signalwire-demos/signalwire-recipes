# Absence reporting line: the caller gives details in any order and code decides when the form is complete

> An absence reporting demo built to show slot filling where the model collects and code decides completeness. One tool with six optional parameters merges each turn, validates dates from spoken words, and opens confirmation only when nothing is missing.

**Scenario:** A parent or employee reports an absence however the details come out, and the agent asks only for what is still missing

## What this demonstrates

Grammar filling: the model collects, but code decides when the form is
complete. `collect` has exactly one tool, `record_slots`, whose six parameters
are all optional, and `valid_steps=[]`, so the model has no `next_step` tool.
Each call merges that turn's values into `global_data["absence"]`, validates
every value in `slots.py`, and answers with what is still missing. Dates are
parsed from the caller's exact words, and an ambiguous "11 2" comes back as
"November 2 or February 11?". Only when nothing is missing does the handler
call `swml_change_step("confirm")`. `submit_report` exists only in `confirm`,
re-checks all six slots from `global_data`, and is the only thing that writes
a report.

The agent takes an absence report with six details. They are the absent
person's name, their student or employee ID, whether it is school or work,
the reason, and the first and last day. The caller can give them in any order,
several at once or one per turn. Dates come as people say them: "Monday",
"tomorrow", "the third of November", "11/3". The agent asks only for what is
missing or unclear, reads the report back, and on a yes saves it and gives
the caller a reference.

## How it works

The contrast with the hiring phone screen is the point. That one uses the
SDK's gather step: questions in a fixed order, one at a time, nothing skipped.
Here the order is the caller's: a slot map plus a merge handler accepts any
subset in any order. Pick gather when the order matters, and grammar filling
when only completeness matters. `slots.py` is copied from the upstream
`patterns/grammar-filling` and `patterns/date-collection` snippets, with dates
without a year defaulting to this year and "today", "tomorrow" and weekday
names understood. Speech-to-text writes "11 2" as "eleven two", so spoken
numbers are parsed too. A name needs two words and no relationship words,
after "son" was once accepted as one.

Where each mechanism lives in the repository:

- `set_functions` and `set_valid_steps([])`: `app.py`, steps `collect`, `confirm`, `done`
- the all-optional tool schema built from `config.SLOTS`: `app.py`, `define_tool("record_slots")`
- the merge, validation and missing-slot gate: `slots.py`, `fill()`; `app.py`, `record_slots`
- date parsing from the caller's words: `slots.py`, `parse_date()`
- `update_global_data` then `swml_change_step`: `record_slots` and `submit_report`
- `${global_data.absence_summary}` in step text: step `confirm`
- `set_prompt_llm_params(model=...)`: `AbsenceAgent.__init__`, from `config.MODEL`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a slot parser. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `proposed`: built, with its live test still to come.

The agent itself is stateless, since the slots live in `global_data`, but
`submit_report` writes to local disk. On Lambda or Cloud Functions, replace
that write with your HR or student-information system. `config.MODEL` defaults
to `gpt-4.1-mini` because on the platform default model `record_slots` was
skipped on most turns during the author's test calls. The code's "November 2
or February 11?" question is covered by a test but not yet seen on a live
call. The model clarified the date itself each time.

## What to change first

Open `config.py` and edit `SLOTS`, the slot list. For a school-only line, drop
`org_type` and call `id` a student ID; for work, add slots such as `manager`
or `shift`, each with a validator (`matches(...)`, `one_of(...)` or
`parse_date`). The tool schema, the missing-slot gate and the saved report all
follow that dict. Then set `ORG_NAME`, and point `REPORTS_DIR` at the system
that should receive the reports.
