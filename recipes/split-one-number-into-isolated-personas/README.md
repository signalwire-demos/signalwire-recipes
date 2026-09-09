# Run isolated personas behind one number

> The default context's step lists sales, support and billing in valid_contexts and names no tools. Each persona is an isolated context, and its step offers the model only that desk's tool.

**Scenario:** a bicycle shop with one number and three desks that must not blur into each other

## What this demonstrates

Contexts do two jobs here. `isolated: true` on a persona context means, per the
bundled schema, that entering it "resets conversation history to only the
system prompt". The support desk does not inherit what the caller told sales.
`functions` on each persona's step names only that desk's tool. All three tools
stay registered under `SWAIG.functions`. The step decides which one the platform
offers the model on a given turn, and a step is not a security boundary. The
`default` context's step names no tools and lists the three personas in
`valid_contexts`. The schema requires a context by that name.

The [contexts reference](https://developer.signalwire.com/swml/methods/ai/prompt/contexts/)
documents contexts and steps; `isolated` is the context field the schema adds
for the wipe.

## How it works

```python
triage = contexts.add_context("default")
triage.add_step("ask") \
    .set_functions([]) \
    .set_valid_contexts(["sales", "support", "billing"])

for name, (prompt, tools) in PERSONAS.items():
    ctx = contexts.add_context(name)
    ctx.set_isolated(True)
    ctx.add_section("Role", prompt)
    ctx.add_step("help").set_functions(tools).set_valid_contexts(["default"]).set_end(True)
```

What the platform receives for the support persona, trimmed:

```json
{"support": {"isolated": true,
             "pom": [{"title": "Role", "body": "You are the workshop support desk ..."}],
             "steps": [{"name": "help", "functions": ["book_repair"],
                        "valid_contexts": ["default"], "end": true, ...}]}}
```

The platform offers the model a `change_context` tool, and `valid_contexts`
limits it to the names listed. Entering support wipes the history, and the step
offers `book_repair` alone. That step's `functions` omits `quote_price` and
`look_up_invoice`, so the platform does not offer them there.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/front-door/`, ask for support, then ask
for a price.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders and validates the SWML, reads `ai.prompt.contexts`, and asserts the
following.

- the contexts are exactly `default`, `sales`, `support` and `billing`
- the default context's step names no functions and lists exactly the three personas in `valid_contexts`, and it omits `isolated`
- each persona context carries `isolated: true` and a `Role` section naming its desk
- each persona has one step whose `functions` is exactly its own tool, with `valid_contexts` back to `default` and `end: true`
- no persona step names another persona's tool, checked before the exact list
- all three tools exist on the agent, so the steps are what scopes them, and each answers with its fixed reply and no action
- the bundled schema documents `isolated` on a context as a boolean that "resets conversation history to only the system prompt"

## Limitations

A step is not a security boundary. `functions` shapes which tools the platform
offers the model; a handler that must not run for the wrong desk checks state
itself.

Isolation wipes what the caller already said, per the schema's description of
`isolated`. You carry what the next desk needs to know some other way.

The three tools are stubs with fixed replies, which the verifier asserts.

## What to change first

Add `"quote_price"` to the support step's `functions` and run the verifier. The
cross-persona assertion fails first, because the support step now names another
persona's tool. What a desk offers is exactly the list on its step, and nothing
else decides it.
