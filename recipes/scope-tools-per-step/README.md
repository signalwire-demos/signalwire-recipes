# Control which tools an AI agent can call at each step

> At each point in the conversation the model can only see the tools you allowed there.

## What this demonstrates

The model cannot call a tool that is not exposed at the current step. The tool is
absent from its world rather than discouraged by an instruction, so neither a
persistent caller nor a prompt injection can reach it.

This is the difference between a rule and a constraint. A prompt saying "do not
transfer before taking a name" is a preference the model may ignore under
pressure. A step that does not list `transfer_to_human` in its functions makes
transferring unavailable.

## How it works

The agent declares one context with two steps. Each step calls
`set_functions([...])` with exactly the tools that may exist while it is active,
and `set_valid_steps([...])` with where it may go next. In the SWML the platform
receives, that becomes a `functions` whitelist on each step under
`ai.prompt.contexts.default.steps`:

```json
{"name": "collect_name",   "functions": ["save_name"],                     "valid_steps": ["collect_reason"]}
{"name": "collect_reason", "functions": ["save_reason", "transfer_to_human"], "valid_steps": ["collect_reason"]}
```

All three tools are defined once on the agent (`ai.SWAIG.functions`); the step
decides which of them the model can see. `save_name` writes the caller's name
to `global_data` from the handler (`set_global_data` action), so the next step
has it without the model relaying it. `transfer_to_human` returns
`FunctionResult(...).connect(address)`, which the platform receives as a `SWML`
action carrying a `connect` verb plus `"transfer": "true"`.

One thing to know: a step that does not call `set_functions` **inherits the
previous step's whitelist**. Declare it on every step.

## Run it

```bash
cd python
pip install -r requirements.txt
SUPPORT_ADDRESS=sip:support@yourspace.sip.signalwire.com python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/intake/`, using the credentials from your `.env` (the agent
prints its URL and Basic Auth on start).

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and asserts the per-step `functions` lists. It then runs each tool
handler and asserts the JSON keys the platform receives (`set_global_data`, `SWML` +
`transfer`), never the SDK method names that produced them.

## Limitations

Step *advancement* is model-evaluated against the step criteria. Tool
*visibility* is not. If the order itself must be guaranteed, force the transition
from inside the tool handler rather than trusting the criteria.

## What to change first

Add a third step and give it a tool the earlier steps must not reach. Then try to
talk the agent into using it early.
