# AI customer survey caller: a prefab agent with validation the handler owns

> A customer survey demo built to show a prefab SurveyAgent configured rather than written. The two tools are overridden with one strict schema, so the handler decides what counts as an answer and what is recorded.

**Scenario:** A customer gets a short follow-up call, answers four questions, and the validated answers land in a file you can score

## What this demonstrates

A known archetype from a prefab, with governance added in two places.
`SurveyAgent` from `signalwire.prefabs` brings the survey prompt, speech hints,
a static greeting, a post-prompt summary and two tools, `validate_response` and
`log_response`; the whole survey is configuration in `config.py`. The recipe
overrides both tools with one shared schema: question ids as an enum from
`config.QUESTIONS`, and both parameters required. The handler, not the model,
decides what counts as an answer. A rating out of range, an option not on the
list or a "maybe" to a yes/no is refused, and nothing is written.

The agent calls, or answers, and runs a four-question survey. The questions
are a 1 to 10 recommend score, a multiple-choice favourite, a yes/no "was your
issue taken care of", and an optional comment. Each answer is checked and
appended to `data/results.jsonl`, and `score_results.py` turns that file into
an NPS-style report. `call_customer.py` starts the survey as an outbound call;
calling the number inbound runs the same survey for testing.

## How it works

The customer id comes from the dial URL (`?customer=`) through the dynamic
config callback, so the model never picks whose row an answer belongs to. The
report is computed from the handler-validated rows, not from the model's
summary. The outbound side is one REST call, `calling.dial(from_, to, url)`.

Where each mechanism lives in the repository:

- `SurveyAgent(survey_name, questions, ...)`: `app.py`, `SurveyCaller.__init__`, questions from `config.QUESTIONS`
- the overridden `validate_response` and `log_response` tools, one shared schema: `app.py`; both normalise and check, `log_response` writes
- `set_dynamic_config_callback` and `update_global_data`: `per_call`, which puts `?customer=` into `global_data`
- REST `calling.dial(from_, to, url)`: `call_customer.py`
- the NPS scoring rule: `score_results.py`, thresholds in `config.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and two helper scripts. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

Answers are appended to a local `data/results.jsonl`, so the app is not suited
to serverless as shipped; point `RESULTS_FILE`, or the write in
`log_response`, at a database first. For a list of customers, loop over
`call_customer.py` from a shell script or cron job. The recipe
`start-from-a-prefab-agent` shows the same prefab's shape without the
overrides.

## What to change first

Open `config.py`: edit `QUESTIONS` (wording, type, options, scale) and
`BRAND_NAME`, `INTRODUCTION` and `CONCLUSION`. Then set the scoring rule:
`NPS_QUESTION`, `PROMOTER_MIN` and `DETRACTOR_MAX`.
