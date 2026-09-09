"""Enforce state transitions in a tool handler.

`valid_steps` shapes the navigation tool the model is offered. It does not
constrain your webhook, and it is not a lock: a step change from a handler
bypasses it. The handler is the last authority on whether the caller moves on,
and the tool that finally acts checks the state again rather than trusting
where it sits in the flow.

This agent takes a repair booking. The caller cannot reach scheduling until a
bike has actually been identified, and the check reads collected state rather
than asking the model whether it collected it.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# What the shop can actually service. Not in the prompt: the model cannot
# widen it by being persuaded.
SERVICEABLE = {"road", "gravel", "hybrid", "mountain"}


class BookingAgent(AgentBase):
    def __init__(self):
        super().__init__(name="booking", route="/booking")
        self.prompt_add_section(
            "Role",
            "You book repair appointments for a bicycle shop. Find out what "
            "kind of bike the caller has, then arrange a drop-off time.",
        )
        contexts = self.define_contexts()
        flow = contexts.add_context("default")

        identify = flow.add_step("identify_bike")
        identify.set_text(
            "Ask what kind of bike the caller needs repaired, and confirm it "
            "back to them before going further."
        )
        identify.set_functions(["record_bike", "start_scheduling"])
        # No native route out. Listing "schedule" here would hand the model a
        # next_step straight past the check below, which is the whole point.
        identify.set_valid_steps([])

        schedule = flow.add_step("schedule")
        schedule.set_text(
            "Offer a drop-off slot for the ${bike_type} the caller described."
        )
        schedule.set_functions(["confirm_slot"])
        schedule.set_valid_steps([])

    @AgentBase.tool(
        name="record_bike",
        description=(
            "Record the kind of bike the caller needs repaired. Call this as "
            "soon as they say what they ride."
        ),
        parameters={
            "type": "object",
            "properties": {
                "bike_type": {
                    "type": "string",
                    "description": (
                        "The kind of bike: road, gravel, hybrid or mountain."
                    ),
                }
            },
            "required": ["bike_type"],
        },
    )
    def record_bike(self, args, raw_data):
        kind = (args.get("bike_type") or "").strip().lower()
        if kind not in SERVICEABLE:
            # Refused, with the reason and what to do instead.
            return FunctionResult(
                f"UNSUPPORTED: the shop does not service {kind or 'that'}. "
                f"Tell the caller which types are serviced "
                f"({', '.join(sorted(SERVICEABLE))}) and ask again."
            )
        # State is written by code, from the validated value.
        return FunctionResult(
            f"Recorded a {kind}."
        ).update_global_data({"bike_type": kind})

    @AgentBase.tool(
        name="start_scheduling",
        description=(
            "Move on to arranging a drop-off time. Call this once the caller's "
            "bike has been recorded."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def start_scheduling(self, args, raw_data):
        # The model may call this whenever it likes. Read the state instead
        # of believing it.
        recorded = (raw_data or {}).get("global_data", {}).get("bike_type")
        if recorded not in SERVICEABLE:
            return FunctionResult(
                "NOT_READY: no serviceable bike has been recorded yet. Ask "
                "what kind of bike it is and call record_bike first."
            )
        return FunctionResult(
            f"Scheduling a drop-off for the {recorded}."
        ).swml_change_step("schedule")

    @AgentBase.tool(
        name="confirm_slot",
        description="Confirm the drop-off slot the caller chose.",
        parameters={
            "type": "object",
            "properties": {
                "slot": {"type": "string",
                         "description": "The slot, such as 'Thursday 9am'."}
            },
            "required": ["slot"],
        },
    )
    def confirm_slot(self, args, raw_data):
        # Reaching this step is not permission to book. A step is a place in a
        # flow, not a security boundary, so the tool that acts checks the state
        # it depends on rather than trusting how the call arrived.
        recorded = (raw_data or {}).get("global_data", {}).get("bike_type")
        if recorded not in SERVICEABLE:
            return FunctionResult(
                "NOT_READY: no serviceable bike has been recorded, so there is "
                "nothing to book. Ask what kind of bike it is and call "
                "record_bike first."
            )
        return FunctionResult(f"Booked a {recorded} for {args.get('slot')}.")


agent = BookingAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
