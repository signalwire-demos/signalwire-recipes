"""Require verification before unlocking tools.

The account tools are declared with `active: False`, so they are not in the
model's tool list when the call starts. Only the verification handler - code,
not the model - turns them on, with a `toggle_functions` action, and only when
the code is right.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

ACCOUNT_TOOLS = ["get_balance", "list_recent_transactions"]

# Your system of record. Keyed by phone number for the demo.
CUSTOMERS = {
    "+15551234567": {"pin": "4242", "balance": "1,204.18",
                     "recent": ["-42.10 grocery", "-9.99 streaming"]},
}


class BankAgent(AgentBase):
    def __init__(self):
        super().__init__(name="bank", route="/bank")
        self.prompt_add_section(
            "Role",
            "You are a bank's phone line. Before anything else, ask for the "
            "caller's four-digit PIN and call verify_pin. Never guess account "
            "details.",
        )

    @AgentBase.tool(
        name="verify_pin",
        description="Check the caller's PIN. Account tools unlock only on success.",
        parameters={"pin": {"type": "string", "description": "Four-digit PIN"}},
    )
    def verify_pin(self, args, raw_data):
        caller = (raw_data or {}).get("caller_id_num", "")
        customer = CUSTOMERS.get(caller)
        if not customer or (args.get("pin") or "").strip() != customer["pin"]:
            # No action: the account tools stay inactive.
            return FunctionResult("That PIN does not match. Please try again.")
        result = FunctionResult("Thank you, you are verified. How can I help?")
        # The unlock is a platform action emitted by code, not a prompt instruction.
        result.toggle_functions([{"function": f, "active": True} for f in ACCOUNT_TOOLS])
        result.toggle_functions([{"function": "verify_pin", "active": False}])
        result.update_global_data({"verified": True})
        return result

    @AgentBase.tool(
        name="get_balance",
        description="Read the verified caller's balance",
        parameters={},
        active=False,   # not in the model's world until verify_pin succeeds
    )
    def get_balance(self, args, raw_data):
        c = CUSTOMERS.get((raw_data or {}).get("caller_id_num", ""))
        if not c:
            return FunctionResult("No account found.")
        return FunctionResult(f"The balance is {c['balance']} dollars.")

    @AgentBase.tool(
        name="list_recent_transactions",
        description="Read the verified caller's last transactions",
        parameters={},
        active=False,
    )
    def list_recent_transactions(self, args, raw_data):
        c = CUSTOMERS.get((raw_data or {}).get("caller_id_num", ""))
        return FunctionResult("; ".join(c["recent"]) if c else "No account found.")


if __name__ == "__main__":
    BankAgent().serve(port=int(os.getenv("PORT", "8080")))
