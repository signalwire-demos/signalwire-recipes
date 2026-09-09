"""Run a Bedrock voice agent.

`BedrockAgent` renders `amazon_bedrock` where `AgentBase` renders `ai`. The
SDK's `agents/bedrock.py` renders the base document, then rebuilds the verb
with the same `prompt` plus `voice_id`, `temperature` and `top_p` inside it.
It copies `SWAIG`, `params`, `global_data` and the post-prompt settings. So
the SWAIG functions render the same on both, and one `configure()` registers
the same handler on each agent. This file configures one parts desk twice,
once on each base class, from that one function.

Written against signalwire-sdk 3.0.1 (AgentBase, BedrockAgent).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, BedrockAgent, FunctionResult

# the SDK does not read .env for you
load_dotenv()

STOCK = {"brake pads": 12, "chain": 4, "tubes": 0}

PARAMETERS = {
    "type": "object",
    "properties": {"part": {
        "type": "string",
        "description": "The part the caller asked about, as they said it."}},
    "required": ["part"],
}


def check_stock(args, raw_data):
    """The handler both agents run. Fixed data, so the reply is checkable."""
    part = args.get("part", "").strip().lower()
    count = STOCK.get(part)
    if count is None:
        return FunctionResult(f"We do not carry {part}.")
    if count == 0:
        return FunctionResult(f"{part} are out of stock. A restock lands Thursday.")
    return FunctionResult(f"{count} {part} in stock.")


def configure(agent):
    """One parts desk, whichever base class it sits on."""
    agent.prompt_add_section(
        "Role",
        "You are the parts desk at Ridgeline Cycles. Check stock before you promise "
        "anything, and say exactly what the check returned.")
    agent.define_tool(
        name="check_stock",
        description="Check whether a bike part is in stock before promising it.",
        parameters=PARAMETERS,
        handler=check_stock,
    )
    return agent


def build(kind="bedrock"):
    """`ai` for the standard agent, `bedrock` for the same desk on Bedrock."""
    if kind == "ai":
        return configure(AgentBase(name="parts", route="/parts"))
    if kind == "bedrock":
        return configure(BedrockAgent(name="parts", route="/parts",
                                      voice_id=os.getenv("BEDROCK_VOICE_ID", "matthew")))
    raise SystemExit(f"AGENT_KIND must be ai or bedrock, not {kind!r}")


agent = build(os.getenv("AGENT_KIND", "bedrock"))

if __name__ == "__main__":
    agent.run()
