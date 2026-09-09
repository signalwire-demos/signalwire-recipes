"""Extract structured data after a call.

The post-prompt runs once, after the conversation ends. Ask it for JSON and the
platform POSTs the result to your post-prompt URL, where `on_summary` receives
it.

The model writes that JSON, so the handler validates it before anything is
stored. A summary that fails validation is quarantined rather than trusted: the
call still happened, and a malformed field is not a reason to lose it.

Written against signalwire-sdk 3.0.1.
"""
import os
import re

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

OUTCOMES = ("resolved", "escalated", "callback_requested", "abandoned")

# what a usable record looks like; anything else is quarantined
REQUIRED = ("outcome", "reason", "callback_number")

filed = []      # records that passed validation
quarantine = [] # everything else, with the reason it failed


class SupportAgent(AgentBase):
    def __init__(self):
        super().__init__(name="support", route="/support")
        self.prompt_add_section(
            "Role",
            "You are the first responder on a support line for a bicycle "
            "retailer. Find out what the caller needs and either solve it or "
            "take a callback number.",
        )
        # Runs after the call. Name the fields and the allowed values; a
        # free-text instruction produces free-text JSON.
        self.set_post_prompt(
            "Return only JSON, no prose, with exactly these keys: "
            '"outcome" (one of resolved, escalated, callback_requested, '
            'abandoned), "reason" (one short sentence), "callback_number" '
            "(E.164, or null if none was given)."
        )

    def on_summary(self, summary, raw_data=None):
        """Called with whatever the post-prompt produced."""
        call_id = (raw_data or {}).get("call_id", "unknown")
        problem = validate(summary)
        if problem:
            quarantine.append({"call_id": call_id, "why": problem,
                               "summary": summary})
            return
        filed.append({"call_id": call_id, **summary})


E164 = re.compile(r"^\+[1-9]\d{1,14}$")


def validate(summary):
    """Return None if the summary is usable, else why it is not."""
    if not isinstance(summary, dict):
        return "not an object"
    missing = [k for k in REQUIRED if k not in summary]
    if missing:
        return f"missing {', '.join(missing)}"
    # The post-prompt asked for exactly these keys. An extra one is the model
    # improvising, and improvised fields are how a schema drifts unnoticed.
    extra = [k for k in summary if k not in REQUIRED]
    if extra:
        return f"unexpected {', '.join(sorted(extra))}"
    if summary["outcome"] not in OUTCOMES:
        return f"outcome {summary['outcome']!r} is not one of {OUTCOMES}"
    if not isinstance(summary["reason"], str) or not summary["reason"].strip():
        return "reason is empty"
    number = summary["callback_number"]
    if summary["outcome"] == "callback_requested" and not number:
        return "callback_requested with no callback_number"
    if number is not None and not E164.match(str(number)):
        return f"callback_number {number!r} is not E.164"
    return None


agent = SupportAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
