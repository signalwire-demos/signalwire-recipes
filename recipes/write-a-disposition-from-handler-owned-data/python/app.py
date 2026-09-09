"""Write a disposition from handler-owned data.

The qualification fields of a disposition come from what your tool handlers
wrote to `global_data` during the call. They are not parsed out of the
transcript, and they are not whatever the model wrote in its end-of-call
summary.

Each handler validates one fact and writes it with a `set_global_data`
action. When the call ends, the platform POSTs to `post_prompt_url` with
`global_data` in the body. `on_summary` builds the record from that POST:
identifiers from the envelope, qualification fields from `global_data`, and
the model's summary as a note that nothing else reads. The record goes to an
in-memory list here; a real handler posts it to your CRM.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# A lead qualifies when the budget clears this and the caller can sign.
MIN_BUDGET = int(os.getenv("MIN_BUDGET", "5000"))

# Every disposition written, newest last. In memory, so a restart loses it; a
# real handler posts each one to your CRM instead.
DISPOSITIONS = []


class QualifierAgent(AgentBase):
    def __init__(self):
        super().__init__(name="qualifier", route="/qualifier")
        self.prompt_add_section(
            "Role",
            "You qualify inbound leads for a fleet bicycle supplier. Find out "
            "the budget, when they need the bikes, and whether the caller can "
            "sign the order. Record each answer with its tool as soon as you "
            "have it.",
        )
        # The model still writes a summary. It is a note on the record, and
        # the disposition is built without reading it.
        self.set_post_prompt(
            "Summarise the call in two sentences of plain prose."
        )

    @AgentBase.tool(
        name="record_budget",
        description="Record the caller's budget in dollars once they state it.",
        parameters={
            "type": "object",
            "properties": {"amount": {"type": "integer",
                                      "description": "Budget in whole dollars."}},
            "required": ["amount"],
        },
    )
    def record_budget(self, args, raw_data):
        amount = args.get("amount")
        if type(amount) is not int or amount <= 0:  # bool is an int in Python
            return FunctionResult("INVALID: ask for the budget as a number of dollars.")
        r = FunctionResult(f"Budget recorded: {amount} dollars.")
        r.add_action("set_global_data", {"budget": amount})
        return r

    @AgentBase.tool(
        name="record_timeline",
        description="Record how many weeks until the caller needs the bikes.",
        parameters={
            "type": "object",
            "properties": {"weeks": {"type": "integer",
                                     "description": "Weeks from today."}},
            "required": ["weeks"],
        },
    )
    def record_timeline(self, args, raw_data):
        weeks = args.get("weeks")
        if type(weeks) is not int or weeks < 0:
            return FunctionResult("INVALID: ask for the timeline in weeks.")
        r = FunctionResult(f"Timeline recorded: {weeks} weeks.")
        r.add_action("set_global_data", {"timeline_weeks": weeks})
        return r

    @AgentBase.tool(
        name="record_decision_maker",
        description="Record whether the caller can sign the order themselves.",
        parameters={
            "type": "object",
            "properties": {"can_sign": {"type": "boolean",
                                        "description": "True if they can sign."}},
            "required": ["can_sign"],
        },
    )
    def record_decision_maker(self, args, raw_data):
        can_sign = args.get("can_sign")
        if not isinstance(can_sign, bool):
            return FunctionResult("INVALID: ask a yes or no question.")
        r = FunctionResult("Recorded." if can_sign else
                           "Recorded. Ask who does sign, for the notes.")
        r.add_action("set_global_data", {"can_sign": can_sign})
        return r

    def on_summary(self, summary, raw_data=None):
        """Build the disposition from what the handlers wrote."""
        raw = raw_data or {}
        data = raw.get("global_data") or {}
        budget = data.get("budget")
        can_sign = data.get("can_sign")
        disposition = {
            "call_id": raw.get("call_id"),
            "caller": raw.get("caller_id_number"),
            "budget": budget,
            "timeline_weeks": data.get("timeline_weeks"),
            "can_sign": can_sign,
            # decided in code from handler-written fields, never from prose
            "qualified": bool(budget and budget >= MIN_BUDGET and can_sign is True),
            # all three expected keys present in global_data
            "complete": all(k in data for k in
                            ("budget", "timeline_weeks", "can_sign")),
            # the model's words, kept as a note and not read by anything above
            "model_note": summary if isinstance(summary, str) else
                          (raw.get("post_prompt_data") or {}).get("raw"),
        }
        DISPOSITIONS.append(disposition)
        return disposition


agent = QualifierAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
