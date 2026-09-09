# Place an outbound AI call

> One REST `dial` carries the agent's SWML inside the request. `direction: outbound` makes the agent the caller, and `wait_for_user: true` makes it wait for the callee to speak first.

**Scenario:** a workshop calling a customer to say their bike is ready

## What this demonstrates

`POST /api/calling/calls` with `command: dial` and the SWML dial variant, which
the vendored REST spec defines with `from` and `swml` required. The document is
an ordinary `AgentBase` rendered with `_render_swml()`. Two entries in its
`ai.params` do two different jobs. The
[ai params reference](https://signalwire.com/docs/swml/reference/ai/params)
says `direction` "forces the direction of the call to the assistant". It says
`wait_for_user: true` means the "agent will wait for the user to speak first".

## How it works

```python
class ReminderAgent(AgentBase):
    def __init__(self):
        super().__init__(name="reminder", route="/reminder")
        self.prompt_add_section("Role", "You are calling from Ridgeline Cycles ...")
        self.set_params({"direction": "outbound", "wait_for_user": True,
                         "outbound_attention_timeout": 20000})

def place(to):
    return client.calling.dial(**{
        "from": FROM, "to": to, "swml": json.loads(agent._render_swml()),
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["ringing", "answered", "ended"], "timeout": 25})
```

What the platform receives, trimmed:

```json
{"command": "dial",
 "params": {"from": "+15550001111", "to": "+15552223333", "timeout": 25,
            "swml": {"version": "1.0.0", "sections": {"main": [{"answer": {}},
              {"ai": {"prompt": {"pom": [...]},
                      "params": {"direction": "outbound", "wait_for_user": true,
                                 "outbound_attention_timeout": 20000}}}]}}}}
```

The bundled schema bounds `outbound_attention_timeout` to 10,000 through
600,000, and the verifier reads that range from the schema. The spec has a
second dial variant, `Calling.CallCreateParamsURL`, that takes `url` in place
of `swml`; this recipe inlines the document instead. The `swml/` surface is a
plain-SWML version of the document with the same two params. The agent's
rendering opens with `answer` and carries a `pom` prompt, which the verifier
asserts.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, your number
python app.py +1XXXXXXXXXX       # the number to call; the script refuses to run without one
```

Point `PUBLIC_URL` at a host you run for the `status_url` callbacks, or remove
the two status keys from `place()`.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls `place()`, and
asserts the following.

- exactly one `POST` to the documented calling path with `command: dial`
- every dial parameter is a documented property of the SWML dial variant, and the required ones are present
- `to` and `from` carry the configured numbers, and the request carries no `url`
- the inline document validates against the bundled schema, opens with `answer`, and its prompt opens with the agent's `Role` section
- `ai.params` carry `direction: outbound` and `wait_for_user: true`
- the spec's `required` for that variant includes `from` and `swml`
- `outbound_attention_timeout` sits inside the range the bundled schema gives
- `status_events` uses only documented event names, and the `swml/` surface validates with the same two params

## Limitations

The verifier proves the request. What the callee hears, and when the agent
first speaks, is a live call.

This agent has no tools, which is what lets the document travel inline. An
agent with tools renders each tool's `web_hook_url` from its own host
(`agent_base.py`, `_build_webhook_url`), so it has to be running somewhere the
platform can reach.

## What to change first

Remove `"direction": "outbound"` from `set_params` and run the verifier. The
params assertion fails, which is the point: the param is what tells the
platform which side of the call the assistant is on.
