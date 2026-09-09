"""Text the caller during the call.

A tool result can carry a SWML document, and that document can run
`send_sms`. A handler that has something the caller should keep, such as an
appointment time, texts it to them from inside the tool result.

The model never sees a phone number. The tool takes no number parameter. The
handler reads the caller's number from `caller_id_num`, which the platform
posts with every tool call. The sending number comes from your environment.
The model's only part is deciding when to call the tool.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# The number the text is sent from. It must be a messaging-enabled number on
# your SignalWire project. There is no placeholder: a text from a number you
# do not own fails, so the app refuses to start without one.
SMS_FROM = os.getenv("SMS_FROM")
if not SMS_FROM or not SMS_FROM.startswith("+"):
    raise SystemExit("SMS_FROM is not set. Put a messaging-enabled number in "
                     "E.164 form in .env (see .env.example).")

SHOP = "Ridgeline Cycles"


class BookingAgent(AgentBase):
    def __init__(self):
        super().__init__(name="booking", route="/booking")
        self.prompt_add_section(
            "Role",
            f"You book workshop appointments for {SHOP}. Agree a day and time "
            "with the caller, then use text_confirmation so they have it in "
            "writing. Do not read phone numbers aloud or ask for one.",
        )

    @AgentBase.tool(
        name="text_confirmation",
        description=(
            "Text the appointment details to the caller's phone once a day and "
            "time are agreed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "appointment": {
                    "type": "string",
                    "description": "The agreed day and time, for example "
                                   "'Thursday 10 September at 2pm'.",
                }
            },
            "required": ["appointment"],
        },
    )
    def text_confirmation(self, args, raw_data):
        # The platform posts the caller's number with every tool call. The
        # model never has it and cannot pass a different one.
        to = (raw_data or {}).get("caller_id_num")
        if not to or not to.startswith("+"):
            return FunctionResult(
                "NO_NUMBER: this caller's number is not available, so no text "
                "was sent. Read the details back to them instead."
            )
        when = (args.get("appointment") or "").strip()
        if not when:
            return FunctionResult("INCOMPLETE: agree a day and time first.")
        body = f"{SHOP}: your workshop appointment is {when}. Reply to this " \
               f"text to change it."
        return FunctionResult(
            "The details are on their way to your phone."
        ).send_sms(to_number=to, from_number=SMS_FROM, body=body,
                   tags=["appointment"])


agent = BookingAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
