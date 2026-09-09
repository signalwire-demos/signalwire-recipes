"""Brief the human before the bridge completes.

The receiving agent hears a summary of the caller before the caller can hear
anything. `connect` takes a `confirm`, which runs on the answering leg once it
picks up and before the two legs are joined.

`confirm` can be a URL or an array of SWML methods inline. Inline is used here
because the briefing is built from state the agent already has, so there is
nothing to fetch.

Whatever the confirm plays is private to the answering leg. That is the whole
point: the caller is still listening to hold audio while the agent is told who
is on the line.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

HUMAN = os.getenv("HUMAN_NUMBER", "+15550100001")

# What the briefing is allowed to mention. This excludes whole fields; it does
# not redact within one, so a value the model wrote into `reason` is spoken as
# it stands.
BRIEFED = ("caller_name", "reason", "account_status")


def briefing_from(state):
    """One sentence, built from collected state and nothing else."""
    name = state.get("caller_name") or "an unidentified caller"
    reason = state.get("reason") or "an unstated reason"
    status = state.get("account_status")
    line = f"Call from {name} about {reason}."
    if status:
        line += f" Account is {status}."
    return line


class IntakeAgent(AgentBase):
    def __init__(self):
        super().__init__(name="intake", route="/intake")
        self.prompt_add_section(
            "Role",
            "You take the caller's name and what they need, then put them "
            "through to a person.",
        )

    @AgentBase.tool(
        name="transfer_to_human",
        description=(
            "Put the caller through to a person. Use this once you have their "
            "name and what they are calling about."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def transfer_to_human(self, args, raw_data):
        state = (raw_data or {}).get("global_data", {}) or {}
        if not state.get("caller_name") or not state.get("reason"):
            # A briefing with nothing in it is worse than no briefing: the
            # agent takes the call expecting context and gets none.
            return FunctionResult(
                "NOT_READY: get the caller's name and what they need, save "
                "them, then transfer."
            )
        # Only the fields chosen above travel into the briefing.
        briefed = {k: state[k] for k in BRIEFED if k in state}
        # FunctionResult.connect() takes no confirm, so the verb is built by
        # hand and handed over as SWML. Assert the keys, not the helper.
        return FunctionResult("Putting you through now.").execute_swml({
            "version": "1.0.0",
            "sections": {
                "main": [
                    {"connect": {
                        "to": HUMAN,
                        # spoken to the answering leg, before the caller is
                        # joined, so the caller never hears it
                        "confirm": [
                            {"play": {"url": f"say:{briefing_from(briefed)}"}}
                        ],
                        "confirm_timeout": 20,
                    }}
                ]
            },
        })


agent = IntakeAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
