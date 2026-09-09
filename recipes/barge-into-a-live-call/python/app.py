"""Barge into a live call.

A third party joins a conference in progress with full audio: everyone hears
them and they hear everyone. It is the loud sibling of coaching, and the fields
that make it loud are the ones coaching turns off.

The important one is `end_on_exit`. Whoever barges in is a visitor, so their
leaving must not take the call down with them.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

ROOM = os.getenv("CONFERENCE_NAME", "support-floor")

# Who may enter a live call. A number that reaches this console is not
# authorisation on its own: ANI is spoofable, so this is a floor rather than
# a door. require-verification-before-unlocking-tools is the version with a
# PIN behind it.
SUPERVISORS = {"+15550100777", "+15550100778"}


def calling_number(raw_data):
    """The caller, preferring state this application controls.

    `global_data` holds what your own handlers wrote, so a check against it is
    a check against something you own. The top-level field is the fallback:
    which of the two the platform populates is not settled by any source we
    hold, so this reads both rather than betting on one.
    """
    data = raw_data or {}
    scoped = data.get("global_data") or {}
    return scoped.get("caller_id_num") or data.get("caller_id_num") or ""

# Rooms a supervisor is allowed into. Barging is audible to the customer, so
# the list is code rather than something the model can widen.
ALLOWED = {"support-floor", "sales-floor"}


class BargeAgent(AgentBase):
    def __init__(self):
        super().__init__(name="barge", route="/barge")
        self.prompt_add_section(
            "Role",
            "You are the console a supervisor talks to. If they ask to join a "
            "call so everyone can hear them, put them in.",
        )

    @AgentBase.tool(
        name="barge_in",
        description=(
            "Join a live call with full audio, heard by the agent and the "
            "customer. Use this only when the supervisor asks to speak to "
            "everyone, not to coach."
        ),
        parameters={
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": (
                        "The floor to join, such as 'support-floor'."
                    ),
                }
            },
            "required": ["room"],
        },
    )
    def barge_in(self, args, raw_data):
        # Barging is audible to the customer, so who is asking matters more
        # than what they asked for. Check that first.
        caller = calling_number(raw_data)
        if caller not in SUPERVISORS:
            return FunctionResult(
                "NOT_AUTHORISED: this number is not a supervisor line. Say "
                "you cannot connect them and end the call."
            )
        room = (args.get("room") or "").strip().lower()
        if room not in ALLOWED:
            return FunctionResult(
                f"NOT_ALLOWED: {room or 'that room'} is not a floor you can "
                f"join. Offer one of {', '.join(sorted(ALLOWED))}."
            )
        return FunctionResult(
            f"Joining {room}. Everyone on the call can hear you."
        ).join_conference(
            name=room,
            # heard by everyone: this is the difference from coaching
            muted=False,
            # and no coach target, which would aim it at one leg
            coach=None,
            # a visitor: leaving must not end the call
            end_on_exit=False,
            start_on_enter=False,
            # the customer should know somebody arrived
            beep="onEnter",
        )


agent = BargeAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
