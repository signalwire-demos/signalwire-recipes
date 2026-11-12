# AI hiring phone screen: a voice form the candidate cannot reorder or skip

> A hiring phone screen demo built to show a gather step asking questions in a fixed order with confirmed read-backs. The platform injects one question at a time, and the handler writes the answers, not the model.

**Scenario:** A candidate is called, or calls in, and answers five screening questions in a fixed order before anything else can happen

## What this demonstrates

A voice form the caller cannot reorder or skip. The `screen` step is a gather,
`set_gather_info` plus `add_gather_question`. The platform injects one question
at a time, in the order of `config.QUESTIONS`, and while it gathers the only
callable tool is the platform's `gather_submit`. The step declares
`set_functions([])` and `valid_steps=[]`, so there is no `next_step` and no
user tool to wander into. `confirm=True` on the error-prone questions makes the
submit schema require a confirmed read-back.

The agent runs a short screen for a warehouse shift lead role: work
authorization, years of experience, earliest start date, pay range and one
open question. It reads the work-authorization and start-date answers back and
waits for a yes. When the last answer is in, it saves the screen to
`data/candidates/<candidate_id>.json` and says a recruiter will follow up.
`call_candidate.py` starts the screen as an outbound call; calling the number
inbound runs the same screen for testing.

## How it works

`completion_action="submit"` moves the call to the `submit` step, whose only
tool reads the answers from `global_data` and writes the file. The candidate
id comes from the dial URL (`?candidate=`) through the dynamic config callback,
so the model never picks the file name. The outbound side is one REST call,
`calling.dial(from_, to, url)`, with the candidate's id in the URL.

Where each mechanism lives in the repository:

- `set_gather_info(output_key, completion_action)`: `app.py`, step `screen`
- `add_gather_question(..., confirm=True)`: one per entry in `config.QUESTIONS`
- `set_functions([])` and `set_valid_steps([])`: steps `screen` and `wrap_up`
- `raw_data["global_data"][OUTPUT_KEY]` then `swml_change_step`: the `submit_screen` handler
- `set_dynamic_config_callback`: `per_call`, which puts `?candidate=` into `global_data`
- REST `calling.dial`: `call_candidate.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a dialer script. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Screens are written to local files in `data/candidates/`, so the app is not
suited to serverless as shipped. Point `CANDIDATES_DIR`, or the write in
`submit_screen`, at your applicant tracking system or object storage first.
The gather step is a 3.7.5 feature. The 3.0.1 schema the recipes here validate
against has no `gather_info`, which is one reason this is a linked build
rather than a recipe.

## What to change first

Open `config.py`: edit `QUESTIONS` (order, wording, `type`, a `prompt` that
pins the answer's shape, and which ones need `confirm=True`), then
`COMPANY_NAME` and `ROLE_TITLE`. Swap `CANDIDATES_DIR` for your applicant
tracking system when you are ready.
