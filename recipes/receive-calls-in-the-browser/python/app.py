"""Receive calls in the browser.

A subscriber is a Fabric resource with an address of its own, and a subscriber
token is what a browser registers with. `POST /api/fabric/resources/subscribers`
requires one field, `email`. `GET /api/fabric/resources/{id}/addresses` lists
the subscriber's addresses, each with a `name` and `channels`.
`POST /api/fabric/subscribers/tokens` requires `reference`, "A string that
uniquely identifies the subscriber. Often it's an email", and answers with
`token` and `refresh_token`. A SWML `connect` whose `to` is the subscriber's
address rings whatever registered with that token; the bundled schema lists a
"Call Fabric Resource address" among the forms `connect.to` takes.

Written against signalwire-sdk 3.0.1 (RestClient.fabric, SWMLService).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

EMAIL = os.getenv("SUBSCRIBER_EMAIL", "dana@ridgeline.example")
DISPLAY_NAME = os.getenv("SUBSCRIBER_NAME", "Dana at the workshop")


def create_subscriber(email=EMAIL, display_name=DISPLAY_NAME):
    """The person, as a Fabric resource. Returns (resource id, address name)."""
    resource = client.fabric.subscribers.create(email=email, display_name=display_name)
    addresses = client.fabric.subscribers.list_addresses(resource["id"]).get("data", [])
    if not addresses:
        raise RuntimeError(f"subscriber {resource['id']} listed no address")
    return resource["id"], addresses[0]["name"]


def browser_token(email=EMAIL):
    """What the browser registers with. `reference` is the subscriber's email."""
    return client.fabric.tokens.create_subscriber_token(reference=email)


def ring(address, service=None):
    """The document a number runs to ring the subscriber's browser."""
    service = service or SWMLService(name="ring", route="/ring")
    service.add_verb("answer", {})
    service.add_verb("play", {"url": "say:Connecting you to the workshop."})
    service.add_verb("connect", {"to": address, "timeout": 30})
    service.add_verb("hangup", {})
    return service


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "subscriber":
        resource_id, address = create_subscriber()
        print(f"resource {resource_id}")
        print(f"address {address}")
    elif len(sys.argv) == 2 and sys.argv[1] == "token":
        print(browser_token())
    elif len(sys.argv) == 3 and sys.argv[1] == "document":
        print(json.dumps(ring(sys.argv[2]).get_document(), indent=2))
    else:
        raise SystemExit("usage: python app.py subscriber | token | document <address>")
