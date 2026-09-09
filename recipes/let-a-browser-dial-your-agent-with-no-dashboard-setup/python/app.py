"""Let a browser dial your agent with no Dashboard setup.

Three REST calls give a running agent an address a browser can dial, with no
Dashboard step. `POST /api/fabric/resources/swml_webhooks` creates a resource
whose `primary_request_url` is the agent's URL; the vendored REST spec
requires that one field. `GET /api/fabric/resources/{id}/addresses` lists the
Fabric addresses the resource got, each with an `id` and a `name`.
`POST /api/fabric/guests/tokens` mints a guest token whose `allowed_addresses`
names that address id, and the response carries `token` and `refresh_token`.
A browser hands that token to the Browser SDK and dials the address.

The agent's URL carries its basic-auth pair, because the resource fetches the
document the same way a number's webhook would.

Written against signalwire-sdk 3.0.1 (RestClient.fabric).
"""
import os
import time

ADDRESS_TRIES = 5          # the address list can lag the create; ask a few times

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

AGENT_URL = os.getenv("AGENT_URL")
if not AGENT_URL:
    raise SystemExit("AGENT_URL is required: the agent's public SWML URL, with its "
                     "basic-auth pair")

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "900"))


def register(name="front-desk", wait=time.sleep):
    """Give the running agent a Fabric address. Returns (resource id, address).

    The spec does not say the address is listed the instant the resource
    exists, so the lookup asks up to ADDRESS_TRIES times, a second apart, and
    fails with a clear message rather than an IndexError."""
    resource = client.fabric.swml_webhooks.create(
        name=name, used_for="calling", primary_request_url=AGENT_URL,
        primary_request_method="POST")
    for attempt in range(ADDRESS_TRIES):
        listed = client.fabric.swml_webhooks.list_addresses(resource["id"])
        addresses = listed.get("data", [])
        if addresses:
            return resource["id"], addresses[0]
        if attempt < ADDRESS_TRIES - 1:
            wait(1)
    raise RuntimeError(f"resource {resource['id']} listed no address after "
                       f"{ADDRESS_TRIES} tries")


def guest_token(address_id, now=None):
    """A token a browser can dial that one address with, for TOKEN_TTL_SECONDS."""
    if now is None:
        now = time.time()
    return client.fabric.tokens.create_guest_token(
        allowed_addresses=[address_id], expire_at=int(now) + TOKEN_TTL_SECONDS)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "register":
        resource_id, address = register()
        print(f"resource {resource_id}")
        print(f"address {address['id']} {address.get('name')}")
    elif len(sys.argv) == 3 and sys.argv[1] == "token":
        print(guest_token(sys.argv[2]))
    else:
        raise SystemExit("usage: python app.py register | token <address_id>")
