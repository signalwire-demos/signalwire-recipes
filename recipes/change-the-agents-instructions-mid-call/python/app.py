"""Change the agent's instructions mid-call.

A tool result can replace the system prompt on the call that is already in
progress. No transfer, no second agent, no new leg: the same conversation
continues under new instructions.

The action key the platform reads is `context_switch`, not the SDK method
name `switch_context`. It takes an object with `system_prompt` and, when you
want the earlier turns summarised into the new context instead of carried
verbatim, `consolidate`. `full_reset` drops them entirely.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

FRONT_DESK_PROMPT = (
    "You answer the phone for a bicycle shop. Find out whether the caller "
    "needs billing or the workshop, then hand over using the matching tool. "
    "Do not answer their question yourself."
)

BILLING_PROMPT = (
    "You are now the billing specialist for Ridgeline Cycles. The caller has "
    "already been identified. Answer questions about invoices, refunds and "
    "payment dates. Do not discuss repairs or parts."
)

REPAIRS_PROMPT = (
    "You are now the workshop coordinator for Ridgeline Cycles. Book, move "
    "or check repair appointments. Do not discuss billing."
)


class FrontDeskAgent(AgentBase):
    """One agent that becomes a specialist once it knows what the call is."""

    def __init__(self):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", FRONT_DESK_PROMPT)

    @AgentBase.tool(
        name="become_billing",
        description=(
            "Use this once the caller says they are calling about an invoice, "
            "a refund or a payment. It changes your instructions so you can "
            "help them directly."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def become_billing(self, args, raw_data):
        # consolidate=True: the platform summarises the turns so far into
        # the new context, so the specialist knows what was said without the
        # front-desk prompt still steering it.
        return FunctionResult("Switching you to billing.").switch_context(
            system_prompt=BILLING_PROMPT, consolidate=True
        )

    @AgentBase.tool(
        name="become_workshop",
        description=(
            "Use this once the caller says they are calling about a repair or "
            "an appointment. It changes your instructions so you can help "
            "them directly."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def become_workshop(self, args, raw_data):
        return FunctionResult("Switching you to the workshop.").switch_context(
            system_prompt=REPAIRS_PROMPT, consolidate=True
        )

    @AgentBase.tool(
        name="start_over",
        description=(
            "Use this only if the caller asks to start again from the "
            "beginning. It clears the conversation so far."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def start_over(self, args, raw_data):
        # full_reset=True: the history is dropped, not summarised, and the
        # front desk's own instructions come back.
        return FunctionResult("Starting over.").switch_context(
            system_prompt=FRONT_DESK_PROMPT, full_reset=True
        )


agent = FrontDeskAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
