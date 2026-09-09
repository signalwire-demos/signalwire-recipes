# Transfer a call without losing context

> State and identity travel with the call, so the next leg already knows who this is.

## What this demonstrates

The caller gives their name and reason once. When the call moves to a second agent,
that agent already has both, with no re-authentication and no repeated intake. Nothing
is serialised into a URL in the hope that the other side parses it.

The platform holds interaction state, so the handoff carries it. On a stateless
CPaaS this is application code you write and maintain yourself.

## How it works

Two agents run on one `AgentServer`: `/intake` and `/billing-specialist`. Both agents set `params.persist_global_data = true`, so the platform saves
`global_data` to a channel variable when one AI session ends and restores it for the
next. They also set `params.transfer_summary = true`, giving the next agent a summary
of the conversation so far.

The intake tool `route_caller` writes what it learned from the handler, not
through the model:

```json
{"set_global_data": {"caller_name": "Dana Whitfield", "intake_reason": "...", "verified": true}}
{"SWML": {"version": "1.0.0", "sections": {"main": [{"transfer": {"dest": "https://<host>/billing-specialist"}}]}}, "transfer": "true"}
```

The transfer URL carries none of the context. The billing agent's prompt reads
it directly, `${global_data.caller_name}` and `${global_data.intake_reason}`, so
its first turn already knows who is calling and why.

One SDK note: in 3.0.1, `FunctionResult.execute_swml(..., transfer=True)` places the
transfer flag *inside* the SWML document. The documented action shape, and what
`FunctionResult.connect()` emits, is a sibling `"transfer": "true"`, so this recipe
builds that action explicitly.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
PUBLIC_URL=https://<your-host> python app.py
```

Point a phone number's SWML webhook at
`https://<user>:<password>@<your-host>/intake/`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders both agents' SWML and asserts:

- `persist_global_data` is set on each
- the intake tool emits a `set_global_data` action and a `SWML` + `transfer`
  action
- no collected value appears in the transfer URL
- the billing prompt reads the same `global_data` keys

## Limitations

Context travels with the call, not with the caller. Recognising a returning caller
across separate calls is a different problem and needs durable storage keyed to the
contact.

## What to change first

Add a field during intake and read it from the receiving agent to find the boundary
of what survives.
