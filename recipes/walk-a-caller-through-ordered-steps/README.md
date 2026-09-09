# Walk a caller through steps they cannot skip

> Every step names one tool. Each step but the last names only its successor, so the `next_step` tool the model is offered has no backward or skip target.

**Scenario:** recording a roadside assistance request, three questions in order

## What this demonstrates

A step is a prompt the model reads while that step is active, plus three fields
around it. `valid_steps` lists where the model's `next_step` tool can go.
`functions` lists the tools that exist while the step is active. `step_criteria`
is the sentence the runtime judges before it advances. The
[steps reference](https://developer.signalwire.com/swml/methods/ai/prompt/contexts/steps/)
documents all three. Each step below names exactly one tool, and each step but the
last names only the step after it, so the flow is a line.

Tool handlers accept the answers and write them to `global_data`. Your handler
decides whether an answer counts before anything is written.

## How it works

Each step is declared once and carries its own edges.

```python
flow.add_step("location") \
    .add_section("Current Task", "Ask where the vehicle is.") \
    .set_step_criteria("save_location has accepted a location.") \
    .set_functions(["save_location"]) \
    .set_valid_steps(["vehicle"])
```

The last step sets `end` instead of `valid_steps`. What the platform receives:

```json
{"name": "location", "text": "...",
 "step_criteria": "save_location has accepted a location.",
 "functions": ["save_location"],
 "valid_steps": ["vehicle"]}
```

Call `set_functions` on every step. The SDK's own note on `set_functions` says a
step that does not declare `functions` inherits the previous step's set. It calls
that the most common bug in multi-step agents.

The handler judges the answer. A location under six characters returns
`INCOMPLETE` and writes nothing; a vehicle needs at least two words. A usable
answer emits `set_global_data`. The last handler records the problem and tells
the model to say the request is recorded. This recipe dispatches nothing.

The SDK closes the flow at build time. A `valid_steps` entry naming a step that
does not exist fails the context builder's `validate()`. The SDK catches that
error during render and logs it as `ai_verb_config_error`, so what you see is a
schema error about a missing prompt. The line naming the step is in the log.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/intake/`.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders and validates the SWML, then asserts the following.

- the three steps appear in order; each names one `functions` entry and carries the exact `step_criteria` sentence
- each step but the last names only its successor in `valid_steps`, so `next_step` has no backward or skip target
- the last step carries `end` and no `valid_steps`
- an inadequate answer returns `INCOMPLETE` with no action; a usable one emits `set_global_data`, tested at the five and six character boundary and at one and two words
- `gather_info` does not appear in the SDK's bundled schema
- the last handler's reply tells the model to say the request is recorded
- a step naming a destination that does not exist fails `validate()`, logs `ai_verb_config_error` naming it, and the render raises a schema error for the missing prompt

## Limitations

A step is not a security boundary. `step_criteria` is a sentence the model judges,
and `valid_steps` shapes the tool it is offered. What the verifier proves is the
document: one tool per step, one edge per step. Anything that must not happen
early belongs in a handler.

The verifier shows `gather_info` is absent from the SDK's bundled schema, so a
document using it cannot be validated offline. This recipe does not use it.

## What to change first

Give `vehicle` a `valid_steps` of `["problem", "location"]` and run the verifier.
It fails on the backward edge: the document now offers the model a way back.
