"""Commit a transaction from a call.

Three tools, one write. `set_order` records what the caller wants in
`global_data` and marks it unconfirmed. `confirm_order` takes the caller's
answer to the readback and marks the order confirmed only when the handler
judges that answer a yes. `commit_order` writes it, once, and only when that
confirmation is on record. The model proposes each step; the handlers decide
whether the step counts, and nothing reaches the order book before a yes the
code accepted.

The handlers read state from `global_data` in `raw_data`, the copy the
platform posts with every tool call, not from anything the model says.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

MENU = {"cargo-rack": 45.00, "puncture-kit": 12.50, "helmet": 89.00}

# The whole normalised answers that count as a yes. Matching is by set
# membership, never substring: "yesterday" and "I can't say yes" are not here.
YES = {"yes", "yep", "yeah", "correct", "that is right", "that is correct",
       "go ahead", "confirm", "confirmed", "yes that is right"}


def normalise(text):
    """Lower-case, expand contractions, drop punctuation and politeness."""
    t = (text or "").lower().replace("that's", "that is").replace("it's", "it is")
    t = "".join(ch if ch.isalnum() or ch == " " else " " for ch in t)
    words = [w for w in t.split() if w not in ("please", "thanks", "thank", "you")]
    return " ".join(words)

# The order book. Keyed by call id, so a call can commit exactly once. A real
# handler writes to your order system here.
ORDERS = {}


class OrderAgent(AgentBase):
    def __init__(self):
        super().__init__(name="orders", route="/orders")
        self.prompt_add_section(
            "Role",
            "You take accessory orders for Ridgeline Cycles. Use set_order when "
            "the caller says what they want, then read the items and total back "
            "and ask if that is right. Pass their exact answer to confirm_order. "
            "Use commit_order only after confirm_order says you may.",
        )

    @AgentBase.tool(
        name="set_order",
        description="Record the items the caller wants. Replaces any earlier list.",
        parameters={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(MENU)},
                    "description": "Catalogue item names.",
                }
            },
            "required": ["items"],
        },
    )
    def set_order(self, args, raw_data):
        items = [i for i in (args.get("items") or []) if i in MENU]
        if not items:
            return FunctionResult("INVALID: none of those are catalogue items. "
                                  "Offer the catalogue.")
        total = round(sum(MENU[i] for i in items), 2)
        r = FunctionResult(f"Order noted: {', '.join(items)}, total {total:.2f}. "
                           "Read it back and ask the caller to confirm.")
        # any new list resets the confirmation
        r.add_action("set_global_data", {"order": {"items": items, "total": total},
                                         "confirmed": False})
        return r

    @AgentBase.tool(
        name="confirm_order",
        description=("Pass the caller's exact words in answer to the readback of "
                     "the items and total."),
        parameters={
            "type": "object",
            "properties": {"answer": {"type": "string",
                                      "description": "What the caller said, verbatim."}},
            "required": ["answer"],
        },
    )
    def confirm_order(self, args, raw_data):
        order = ((raw_data or {}).get("global_data") or {}).get("order")
        if not order:
            return FunctionResult("INCOMPLETE: there is no order to confirm yet.")
        readback = f"{', '.join(order['items'])} for {order['total']:.2f}"
        if normalise(args.get("answer")) not in YES:
            return FunctionResult(f"NOT_A_YES: the caller did not clearly agree to "
                                  f"{readback}. Ask again or change the order.")
        r = FunctionResult(f"Confirmed: {readback}. You may commit it now.")
        r.add_action("set_global_data", {"confirmed": True})
        return r

    @AgentBase.tool(
        name="commit_order",
        description="Place the confirmed order. Only after confirm_order.",
        parameters={"type": "object", "properties": {}},
    )
    def commit_order(self, args, raw_data):
        raw = raw_data or {}
        data = raw.get("global_data") or {}
        call_id = raw.get("call_id")
        if call_id in ORDERS:
            # the model asked twice; the book already has it
            return FunctionResult(f"ALREADY_PLACED: order {ORDERS[call_id]['id']} "
                                  "is on file. Do not place it again.")
        if not data.get("order"):
            return FunctionResult("INCOMPLETE: take the order first.")
        if data.get("confirmed") is not True:
            return FunctionResult("NOT_CONFIRMED: read the order back and get a yes "
                                  "before committing.")
        order_id = f"RC-{len(ORDERS) + 1001}"
        ORDERS[call_id] = {"id": order_id, **data["order"]}
        r = FunctionResult(f"Placed as {order_id}. Tell the caller the number.")
        r.add_action("set_global_data", {"order_id": order_id})
        return r


agent = OrderAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
