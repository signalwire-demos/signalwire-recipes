"""Place an outbound AI call.

One REST `dial` command carries the agent's SWML inside the request. Two
`params` on the `ai` verb do two jobs. `direction: outbound` forces the call's
direction to the assistant, which makes the agent the caller. `wait_for_user:
true` makes the agent wait for the callee to speak first. Both are documented
in the ai params reference.

The agent is an ordinary AgentBase; `_render_swml()` gives the document the
platform would otherwise fetch from it.

Written against signalwire-sdk 3.0.1 (AgentBase + RestClient.calling).
"""
import json
import os

from dotenv import load_dotenv
from signalwire import AgentBase
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")


class ReminderAgent(AgentBase):
    def __init__(self):
        super().__init__(name="reminder", route="/reminder")
        self.prompt_add_section(
            "Role",
            "You are calling from Ridgeline Cycles to say the caller's bike is "
            "ready for collection. Wait for them to speak, greet them, say the "
            "bike is ready, ask when they would like to collect it, then say "
            "goodbye.",
        )
        # direction makes the agent the caller; wait_for_user makes it wait
        # for the callee's first words rather than speaking into the ring
        self.set_params({"direction": "outbound", "wait_for_user": True,
                         "outbound_attention_timeout": 20000})


agent = ReminderAgent()
client = RestClient()


def call_document():
    """The agent's SWML, ready to travel inside the dial request."""
    return json.loads(agent._render_swml())


def place(to):
    return client.calling.dial(**{
        "from": FROM,
        "to": to,
        "swml": call_document(),
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["ringing", "answered", "ended"],
        "timeout": 25,
    })


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2 or not sys.argv[1].startswith("+"):
        raise SystemExit("usage: python app.py +1XXXXXXXXXX   (the number to call)")
    print(place(sys.argv[1]))
