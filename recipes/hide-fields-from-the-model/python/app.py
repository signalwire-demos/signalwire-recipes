"""Hide fields from the model.

The record is loaded in full server-side. Only an explicit allowlist projection is
returned to the model, so withheld fields are absent rather than forbidden.

Written against signalwire-sdk 3.0.1.
"""
import json
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# Everything the model is ever allowed to see about a customer. Adding a field
# here is a code review, not a prompt edit.
EXPOSED = ("first_name", "plan", "renewal_date", "open_tickets")


def load_customer(phone):
    """Your system of record. Returns far more than the model should see."""
    return {
        "first_name": "Dana",
        "last_name": "Whitfield",
        "plan": "Business",
        "renewal_date": "2026-11-04",
        "open_tickets": 1,
        # --- none of the below ever reaches the model ---
        "risk_score": 0.82,
        "margin_pct": 11.4,
        "internal_notes": "Threatened to churn in March. Do not offer a discount.",
        "card_last_four": "6411",
    }


def project(record, allow=EXPOSED):
    """The projection is the security boundary."""
    return {k: record[k] for k in allow if k in record}


class AccountAgent(AgentBase):
    def __init__(self):
        super().__init__(name="account", route="/account")
        self.prompt_add_section(
            "Role",
            "You help callers with their account. Answer only from the data the "
            "get_account tool gives you. If a detail is absent, say you do not "
            "have it.",
        )

    @AgentBase.tool(
        name="get_account",
        description="Look up the calling customer's account",
        parameters={},
    )
    def get_account(self, args, raw_data):
        raw = raw_data or {}
        caller = raw.get("caller_id_num") or raw.get("caller_id_number") or ""
        record = load_customer(caller)
        # The model receives the projection as the tool's response text.
        return FunctionResult(json.dumps(project(record)))


if __name__ == "__main__":
    AccountAgent().serve(port=int(os.getenv("PORT", "8080")))
