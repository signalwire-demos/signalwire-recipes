"""Prove the claim without a network.

Claim: livekit-agents-shaped code, an `Agent` with `instructions` and a
`@function_tool`, an `AgentSession` and an `rtc_session` entrypoint, renders a
SignalWire agent through `signalwire.livewire`. The instructions become the
prompt, the tool becomes a SWAIG function with parameters from its type hints,
and the same Python function runs when the tool is called.

Proof: run the entrypoint offline with a `JobContext` and take the `AgentBase`
it leaves in `ctx._agent`. Its rendered document validates and holds one `ai`
verb whose prompt text is the instructions. `SWAIG.functions` has exactly one function,
`opening_hours`, with a `day` string parameter, required, and the docstring as
its description. Executing it through the agent returns the same strings the
Python function returns for a known day, a closed day and an unknown day. The
verifier also shows two 3.0.1 edges: a default `AgentSession` renders an
`attention_timeout` of 3000, below the schema's minimum of 10,000, so its
document fails validation, and a `session.say()` before the build leaves no
trace when instructions are set. Expected values live here, not in app.py.
"""
import asyncio
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")

import verifylib as V  # noqa: E402

INSTRUCTIONS = ("You are the front desk at Ridgeline Cycles. Answer questions about "
                "opening hours with the opening_hours tool, and keep answers short.")
GREETING = "Thanks for calling Ridgeline Cycles. How can I help?"
REPLIES = {"Thursday": "On Thursday the shop is open from 9 to 8.",
           "sunday": "The shop is closed on sunday.",
           "Funday": "I do not have hours for Funday."}


def main():
    V.sdk_banner()
    import app as recipe
    from signalwire.livewire import JobContext

    # a fresh context has no agent: run_app would log "no agent was started"
    ctx = JobContext()
    assert ctx._agent is None
    asyncio.run(recipe.entrypoint(ctx))
    agent = ctx._agent
    assert agent is not None, "the entrypoint must leave the AgentBase in ctx._agent"
    V.assert_basic_auth_from_env(agent)

    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "ai"], V.verb_names(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]

    # the instructions are the prompt, and the delays render as params in range
    prompt = ai["prompt"]
    assert prompt == {"text": INSTRUCTIONS}, prompt
    assert ai["params"] == {"end_of_speech_timeout": 500, "attention_timeout": 15000}, ai["params"]
    defs = V.swml_schema()["$defs"]
    bounds = defs["AIParams"]["properties"]
    assert bounds["end_of_speech_timeout"]["minimum"] == 250
    # both ends of the range the README quotes, from the schema's own definition
    att = defs["AttentionTimeout"]
    assert att.get("minimum") == 10000 and att.get("maximum") == 600000, att
    assert "10,000" in bounds["attention_timeout"]["description"]
    assert "600,000" in bounds["attention_timeout"]["description"]

    # the two 3.0.1 edges: default delays render out of range, and say() is dropped
    from signalwire.livewire import Agent, AgentSession
    default_session = AgentSession()
    plain = Agent(instructions=INSTRUCTIONS, tools=[recipe.opening_hours])
    asyncio.run(default_session.start(plain))
    default_session.say(GREETING)
    default_doc = json.loads(default_session._build_sw_agent()._render_swml())
    default_ai = next(v for v in default_doc["sections"]["main"] if "ai" in v)["ai"]
    assert default_ai["params"]["attention_timeout"] == 3000, default_ai["params"]
    try:
        V.validate_swml(default_doc)
    except AssertionError:
        pass
    else:
        raise AssertionError("a default AgentSession rendered a valid document; the edge is gone")
    assert GREETING not in json.dumps(default_ai["prompt"]), default_ai["prompt"]

    # the tool, from the function's type hints and docstring
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["function"] == "opening_hours", fn
    assert fn["description"] == "Look up the shop's opening hours for a day of the week.", fn
    assert fn["parameters"] == {"type": "object",
                                "properties": {"day": {"type": "string", "description": "day"}},
                                "required": ["day"]}, fn["parameters"]

    # the same Python function answers through the agent
    for day, reply in REPLIES.items():
        got = agent._execute_swaig_function("opening_hours", {"day": day}, call_id="c1")
        assert got == {"response": reply}, (day, got)
        assert recipe.opening_hours(day) == reply, day
    # and it is that function, not a copy: change the table it reads and the
    # agent's answer changes with it (sol r1)
    recipe.HOURS["monday"] = "noon to 1"
    try:
        got = agent._execute_swaig_function("opening_hours", {"day": "Monday"}, call_id="c1")
        assert got == {"response": "On Monday the shop is open from noon to 1."}, got
    finally:
        recipe.HOURS["monday"] = "9 to 6"

    # a type-hinted parameter with a default is optional; one without is required
    from signalwire.livewire import function_tool

    @function_tool
    def hours_for(day: str, style: str = "short") -> str:
        """Hours for a day, short or long."""
        return f"{day}: {style}"

    opt_session = AgentSession(max_endpointing_delay=15.0)
    opt_agent = Agent(instructions=INSTRUCTIONS, tools=[hours_for])
    asyncio.run(opt_session.start(opt_agent))
    opt_doc = json.loads(opt_session._build_sw_agent()._render_swml())
    opt_ai = next(v for v in opt_doc["sections"]["main"] if "ai" in v)["ai"]
    (opt_fn,) = opt_ai["SWAIG"]["functions"]
    assert set(opt_fn["parameters"]["properties"]) == {"day", "style"}, opt_fn["parameters"]
    assert opt_fn["parameters"]["required"] == ["day"], opt_fn["parameters"]

    print(f"ok: the rtc_session entrypoint leaves an AgentBase in ctx._agent whose ai verb carries "
          f"the instructions and one SWAIG function, opening_hours(day), answering "
          f"{REPLIES['Thursday']!r}; a default session renders attention_timeout 3000, out of range")


if __name__ == "__main__":
    main()
