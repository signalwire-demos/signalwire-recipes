"""Test an agent offline with swaig-test.

`swaig-test` ships with the SDK. Pointed at this file it loads the agent. It
prints the SWML the platform would fetch, lists the tools, and runs any tool
with the arguments you give it and fake call data. None of that needs a
number, a tunnel or an account. The agent below is ordinary; nothing in it
knows about the CLI.

Written against signalwire-sdk 3.0.1 (swaig-test, cli/test_swaig.py).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

HOURS = {
    "monday": "8 to 6", "tuesday": "8 to 6", "wednesday": "8 to 6",
    "thursday": "8 to 8", "friday": "8 to 6", "saturday": "9 to 5",
}


class HoursAgent(AgentBase):
    def __init__(self):
        super().__init__(name="hours", route="/hours")
        self.prompt_add_section(
            "Role",
            "You answer questions about Ridgeline Cycles' opening hours. Use "
            "check_hours for the day the caller asks about.",
        )

    @AgentBase.tool(
        name="check_hours",
        description="Look up the shop's opening hours for a day of the week.",
        parameters={
            "type": "object",
            "properties": {
                "day": {"type": "string",
                        "description": "A day of the week, in English."}
            },
            "required": ["day"],
        },
    )
    def check_hours(self, args, raw_data):
        day = (args.get("day") or "").strip().lower()
        if day == "sunday":
            return FunctionResult("The shop is closed on Sunday.")
        hours = HOURS.get(day)
        if not hours:
            return FunctionResult("INVALID: ask for a day of the week.")
        return FunctionResult(f"On {day.title()} the shop is open {hours}.")


agent = HoursAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
