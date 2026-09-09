"""Stream agent debug events.

`enable_debug_events()` puts `debug_webhook_url` and `debug_webhook_level`
into the document's `params`, pointed at the agent's own `/debug_events`
route. The platform POSTs each selected event there during the call, behind
the same basic auth as the rest of the agent. The handler you register with
`on_debug_event` receives every one as it lands.

The level selects the events. Per the SDK, level 1 carries barge, errors,
session start and end, and step changes; level 2 adds every LLM request and
response. Level 2 is a lot of traffic through a tunnel. Turn it on for one
failing call, not for a fleet.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", "1"))

# Every event the handler saw, oldest first: (event_type, call_id), and the
# llm_error events on their own. A real handler forwards these to your
# logging or paging.
EVENTS = []
ERROR_EVENTS = []


class WatchedAgent(AgentBase):
    def __init__(self):
        super().__init__(name="watched", route="/watched")
        self.prompt_add_section(
            "Role",
            "You take messages for a bicycle workshop. Ask for the caller's "
            "name and what they need, then say the workshop will call back.",
        )
        # writes params.debug_webhook_url and params.debug_webhook_level
        # into the rendered document
        self.enable_debug_events(level=DEBUG_LEVEL)


agent = WatchedAgent()


@agent.on_debug_event
def watch(event_type, data):
    """Called for every event the platform POSTs to /debug_events."""
    EVENTS.append((event_type, data.get("call_id")))
    if event_type == "llm_error":
        # the one event worth paging someone for
        ERROR_EVENTS.append({"call_id": data.get("call_id"), "detail": data})


if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
