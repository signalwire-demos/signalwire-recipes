"""Give an agent a tool.

A SWAIG function is not a separate concept from an LLM tool. It is rendered into
the same OpenAI-format tool schema the model sees every turn, so `name`,
`description` and the per-parameter descriptions are what decide whether the
model calls it and how it fills the arguments.

The handler returns a FunctionResult, never a raw string, and returns a typed
state when the lookup fails so the model is told what to do instead of guessing.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# Your system of record. A real one is a database call.
ORDERS = {
    "48815": {"status": "out for delivery", "eta": "today before 8pm",
              "carrier": "Britewave"},
    "48816": {"status": "packed", "eta": "ships tomorrow",
              "carrier": "Britewave"},
}


class OrderAgent(AgentBase):
    def __init__(self):
        super().__init__(name="orders", route="/orders")
        self.prompt_add_section(
            "Role",
            "You answer questions about orders for a home goods retailer. "
            "Look the order up before you say anything about its status. "
            "If the tool says the order was not found, ask the caller to "
            "read the number back to you.",
        )

    # The decorator registers the function. `parameters` is a JSON Schema
    # dict; there is no AgentBase.parameter() helper.
    @AgentBase.tool(
        name="get_order_status",
        description=(
            "Look up the delivery status of a customer's order by its order "
            "number. Use this BEFORE stating any status, date or carrier. "
            "Do not use it for returns or refunds."
        ),
        parameters={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": (
                        "The order number, exactly five digits, no letters "
                        "or dashes. Ask the caller to read it out if they "
                        "have not given it."
                    ),
                }
            },
            "required": ["order_id"],
        },
        # the caller hears one of these while the lookup runs
        fillers={"en-US": ["Let me pull that order up.",
                           "Checking on that order now."]},
    )
    def get_order_status(self, args, raw_data):
        order_id = (args.get("order_id") or "").strip()
        order = ORDERS.get(order_id)
        if not order:
            # A typed failure. The model is told what to do next, so it does
            # not invent a delivery date to fill the silence.
            return FunctionResult(
                f"NOT_FOUND: no order {order_id}. Ask the caller to read the "
                "five digit order number back, then try again."
            )
        # Format for speech here, not in the prompt.
        return FunctionResult(
            f"Order {order_id} is {order['status']}, arriving {order['eta']} "
            f"with {order['carrier']}."
        )


agent = OrderAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
