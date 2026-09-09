"""Whisper to an agent mid-call.

A supervisor joins the conference as a coach. The agent hears them; the customer
does not.

`coach` is the mechanism, and it takes the call ID of a participant already in
the room. That is the whole trick: coaching is aimed at a call, not at the
conference, so the platform knows which one leg to mix the supervisor into.

The supervisor's leg is muted to the room. Coaching audio is not muting's
opposite: without `coach`, an unmuted supervisor is simply a third person in
the meeting.

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

# Who is on the floor. A real deployment reads this from the platform's
# conference status callbacks; see build-a-conference-call.
ON_CALL = {
    "dana": "CA1111111111111111111111111111aaaa",
    "reza": "CA2222222222222222222222222222bbbb",
}


class SupervisorAgent(AgentBase):
    def __init__(self):
        super().__init__(name="supervisor", route="/supervisor")
        self.prompt_add_section(
            "Role",
            "You are the console a supervisor talks to. Ask which agent they "
            "want to coach, then put them through.",
        )

    @AgentBase.tool(
        name="coach_agent",
        description=(
            "Put the supervisor into an agent's live call as a coach, heard "
            "only by that agent. Use this when they name an agent to help."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": (
                        "The agent's first name, lowercase, such as 'dana'."
                    ),
                }
            },
            "required": ["agent"],
        },
    )
    def coach_agent(self, args, raw_data):
        # Check who is asking before resolving who they want. Reaching this
        # agent is not permission to listen to a customer.
        caller = calling_number(raw_data)
        if caller not in SUPERVISORS:
            return FunctionResult(
                "NOT_AUTHORISED: this number is not a supervisor line. Say "
                "you cannot connect them and end the call."
            )
        who = (args.get("agent") or "").strip().lower()
        call_id = ON_CALL.get(who)
        if not call_id:
            # Coaching a call that is not there would join the supervisor as
            # an ordinary participant, audible to the customer.
            return FunctionResult(
                f"NOT_ON_A_CALL: {who or 'that agent'} is not on the floor. "
                f"Say who is available ({', '.join(sorted(ON_CALL))}) and ask "
                f"again."
            )
        return FunctionResult(
            f"Putting you through to {who}. They can hear you; the caller "
            f"cannot."
        ).join_conference(
            name=ROOM,
            # aimed at one leg, which is what makes this coaching
            coach=call_id,
            # silent to the room; only the coached leg hears the supervisor
            muted=True,
            # a supervisor arriving must not announce itself to the customer
            beep="false",
            # and leaving must not end the customer's call
            end_on_exit=False,
            start_on_enter=False,
        )


agent = SupervisorAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
