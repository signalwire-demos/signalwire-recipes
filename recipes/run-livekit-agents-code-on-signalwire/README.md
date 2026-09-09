# Run LiveKit Agents code on SignalWire

> LiveKit-agents-shaped code, an `Agent` with `instructions` and a `@function_tool`, an `AgentSession` and an `rtc_session` entrypoint, renders a SignalWire agent through `signalwire.livewire`. The instructions become the prompt, the tool becomes a SWAIG function, and the same Python function runs when the tool is called.

**Scenario:** a front desk you wrote for livekit-agents that you want on SignalWire without rewriting the tool

## What this demonstrates

`signalwire.livewire` mirrors the livekit-agents names, and its module docstring
says to change the import path and nothing else. In 3.0.1 the mapping is one
method, `AgentSession._build_sw_agent()`, which builds an `AgentBase`. The
`Agent`'s `instructions` become the prompt text. Each `@function_tool` becomes
a SWAIG function through `define_tool`. The name is the function's, the
description is its docstring, and the parameters come from its type hints, each
required unless it has a default. The session's endpointing delays become
`ai.params`. LiveWire accepts the pipeline arguments livekit code passes,
`stt`, `tts`, `vad` and `turn_detection`, and logs them as no-ops, because the
platform does that work.

## How it works

```python
@function_tool
def opening_hours(day: str) -> str:
    """Look up the shop's opening hours for a day of the week."""
    ...

@server.rtc_session(agent_name="front-desk")
async def entrypoint(ctx: JobContext):
    agent = Agent(instructions="You are the front desk at Ridgeline Cycles. ...",
                  tools=[opening_hours])
    session = AgentSession(max_endpointing_delay=15.0)   # renders attention_timeout 15000
    await session.start(agent, room=ctx.room)
    ctx._agent = session._build_sw_agent()   # run_app runs whatever is here

cli.run_app(server)
```

What the platform receives, inside the `ai` verb:

```json
{"prompt": {"text": "You are the front desk at Ridgeline Cycles. ..."},
 "params": {"end_of_speech_timeout": 500, "attention_timeout": 15000},
 "SWAIG": {"functions": [{"function": "opening_hours",
                          "description": "Look up the shop's opening hours for a day of the week.",
                          "parameters": {"type": "object",
                                         "properties": {"day": {"type": "string", "description": "day"}},
                                         "required": ["day"]}, ...}]}}
```

Two lines are SignalWire's rather than LiveKit's. In 3.0.1 `run_app` runs the
`AgentBase` it finds in `ctx._agent` and logs "no agent was started" if the
entrypoint left nothing there. Nothing else builds it. So the entrypoint
calls `session._build_sw_agent()` and assigns the result. And
`max_endpointing_delay` becomes `attention_timeout` in milliseconds, which the
bundled schema bounds at 10,000 to 600,000. The LiveKit default of 3.0 seconds
renders 3000, which the schema rejects, so the session sets 15.0. LiveWire
builds its agent with schema validation off, which is why that default does not
fail loudly on its own.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: the basic-auth pair
python app.py                    # banner, tip, then the agent on port 3000
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. `_build_sw_agent` mounts the agent
at the root route, so point a number's SWML webhook at
`https://<user>:<password>@<your-host>/` and ask what time the shop opens on
Thursday.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier runs the entrypoint offline with a `JobContext` and asserts the
following.

- a fresh `JobContext` has no agent, and after the entrypoint it holds an `AgentBase`
- the rendered document validates, its verbs are `answer`, `ai`, and the prompt is exactly the instructions as `text`
- `ai.params` is exactly `end_of_speech_timeout` 500 and `attention_timeout` 15000, and the schema's bounds are what the prose says
- a default `AgentSession` renders `attention_timeout` 3000 and its document fails validation
- a `session.say()` before the build leaves no trace in the prompt when instructions are set
- `SWAIG.functions` is exactly one function, `opening_hours`, with the docstring as its description and a required `day` string parameter
- executing it through the agent for Thursday, Sunday and an unknown day returns the same three strings the Python function returns

## Limitations

You prove the rendered agent and the tool. What LiveKit-specific code beyond
this shape does is a per-feature question. `AgentSession.interrupt()`,
`JobContext.connect()` and the pipeline arguments are no-ops with a logged
notice, and `mcp_servers` logs that it is not supported.

The parameter descriptions are the parameter names, because LiveWire builds
them from type hints and has no other text to use. A caller-facing description
needs the SignalWire `define_tool` route instead.

The build drops a `session.say()` made before it when `instructions` are set. It
sets the instructions as prompt text, then adds the greeting as a prompt
section, and text wins. Put the greeting in the instructions.

## What to change first

Delete the `ctx._agent = session._build_sw_agent()` line and run the verifier.
The first assertion after the entrypoint fails, because nothing built the agent.
That line is the seam between the two SDKs.
