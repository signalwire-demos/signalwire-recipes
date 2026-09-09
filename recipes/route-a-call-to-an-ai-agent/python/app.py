"""Route a phone number to an AI agent.

Two requests. The first makes a SWML webhook resource that points at your
agent's URL; the second attaches a phone number you already own to it.

The indirection is the point. The number is bound to a resource, not to a URL,
so moving the agent is one PATCH of the resource rather than a change on every
number pointing at it.

Written against signalwire-sdk 3.0.1 (RestClient.fabric).
"""
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

AGENT_URL = os.getenv("AGENT_URL", "https://your-host.example.com/agent")
PHONE_ROUTE_ID = os.getenv("PHONE_ROUTE_ID", "00000000-0000-0000-0000-000000000000")


def point_number_at(agent_url=AGENT_URL, phone_route_id=PHONE_ROUTE_ID):
    """Create the resource, then bind the number to it."""
    resource = client.fabric.swml_webhooks.create(
        name="support agent",
        # where SignalWire fetches the document when a call arrives
        primary_request_url=agent_url,
        primary_request_method="POST",
        # a second URL for SignalWire to try if the primary request fails.
        # Host it apart from the agent, or it shares the outage it covers.
        fallback_request_url=os.getenv("FALLBACK_URL", f"{agent_url}/fallback"),
        fallback_request_method="POST",
    )
    client.fabric.resources.assign_phone_route(
        resource["id"],
        phone_route_id=phone_route_id,
        # this resource answers calls, not messages
        handler="calling",
    )
    return resource


if __name__ == "__main__":
    print(point_number_at())
