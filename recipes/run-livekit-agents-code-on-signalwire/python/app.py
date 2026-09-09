"""Run LiveKit-agents code on SignalWire.

`signalwire.livewire` mirrors the livekit-agents names: `Agent`,
`AgentSession`, `function_tool`, `AgentServer`, `JobContext`, `cli.run_app`.
The module docstring says "just change the import path". This file is that
shape: an `Agent` with `instructions` and one `@function_tool`, an
`AgentSession` started inside an `rtc_session` entrypoint, and `run_app`.

What LiveWire does with it in 3.0.1: `AgentSession._build_sw_agent()` turns
the session into an `AgentBase`. The instructions become the prompt text, each
`@function_tool` becomes a SWAIG function whose parameters come from the
Python type hints. `run_app` then runs whatever the entrypoint left in
`ctx._agent`, so the entrypoint builds it and hands it over; `run_app` does not
build it for you, and logs "no agent was started" if nothing did. Two 3.0.1
edges the verifier shows: the LiveKit default `max_endpointing_delay` renders
an `attention_timeout` below the schema's minimum, and `session.say()` before
the build is dropped when `instructions` are set, because prompt text wins over
the section it would add.

Written against signalwire-sdk 3.0.1 (signalwire.livewire).
"""
from dotenv import load_dotenv
from signalwire.livewire import Agent, AgentServer, AgentSession, JobContext
from signalwire.livewire import cli_ns as cli
from signalwire.livewire import function_tool

# the SDK does not read .env for you
load_dotenv()

HOURS = {"monday": "9 to 6", "tuesday": "9 to 6", "wednesday": "9 to 6",
         "thursday": "9 to 8", "friday": "9 to 6", "saturday": "10 to 4",
         "sunday": "closed"}


@function_tool
def opening_hours(day: str) -> str:
    """Look up the shop's opening hours for a day of the week."""
    hours = HOURS.get(day.strip().lower())
    if hours is None:
        return f"I do not have hours for {day}."
    if hours == "closed":
        return f"The shop is closed on {day}."
    return f"On {day} the shop is open from {hours}."


server = AgentServer()


def build_session():
    """The LiveKit shape: an Agent with instructions and a tool, and a session."""
    agent = Agent(
        instructions=("You are the front desk at Ridgeline Cycles. Answer questions "
                      "about opening hours with the opening_hours tool, and keep "
                      "answers short."),
        tools=[opening_hours],
    )
    # 3.0.1 maps max_endpointing_delay to ai.params.attention_timeout in ms,
    # which the bundled schema bounds at 10,000 to 600,000; the LiveKit default
    # of 3.0 seconds renders 3000 and fails validation, so set it in range
    session = AgentSession(max_endpointing_delay=15.0)
    return agent, session


@server.rtc_session(agent_name="front-desk")
async def entrypoint(ctx: JobContext):
    agent, session = build_session()
    await session.start(agent, room=ctx.room)
    # LiveWire's run_app runs ctx._agent; the session builds it from the Agent
    ctx._agent = session._build_sw_agent()


if __name__ == "__main__":
    cli.run_app(server)
