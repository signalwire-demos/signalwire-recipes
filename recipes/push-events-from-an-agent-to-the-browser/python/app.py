"""Push events from an agent to the browser.

A tool result can carry a SWML `user_event`, whose `event` is any JSON object.
The bundled schema describes it as sending events "to the connected client on
the call". A page running the Browser SDK and subscribed to user events can
receive the structured event. The handler validates the supplied slot id and
chooses the event payload, so the event carries the handler's fields rather
than the model's paraphrase of them.

`FunctionResult.swml_user_event(event)` wraps the verb in a one-verb SWML
document and adds it as a `SWML` action. Your backend can push the same shape
with the REST command `calling.user_event`, whose spec variant requires
`params.event` (tools/openapi/rest.json, Calling.CallRequest).

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

SLOTS = {"thu-14": "Thursday 2pm", "fri-10": "Friday 10am", "sat-09": "Saturday 9am"}


class BookingAgent(AgentBase):
    def __init__(self):
        super().__init__(name="booking", route="/booking")
        self.prompt_add_section(
            "Role",
            "You book workshop slots for Ridgeline Cycles from a web page that "
            "shows the available times. Use select_slot when the caller picks one.",
        )

    @AgentBase.tool(
        name="select_slot",
        description="Record which workshop slot the caller has chosen.",
        parameters={
            "type": "object",
            "properties": {"slot": {"type": "string", "enum": sorted(SLOTS),
                                    "description": "The slot id shown on the page."}},
            "required": ["slot"],
        },
    )
    def select_slot(self, args, raw_data):
        slot = args.get("slot")
        if slot not in SLOTS:
            return FunctionResult("INVALID: that slot is not on the page.")
        # the event carries the selection as data; the response is a sentence
        return FunctionResult(
            f"Noted {SLOTS[slot]} for the caller."
        ).swml_user_event({"type": "slot_selected", "slot": slot, "label": SLOTS[slot]})


agent = BookingAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
