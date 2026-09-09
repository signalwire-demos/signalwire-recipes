"""Register a SIP endpoint and receive calls.

A subscriber's SIP credential is a username and password a softphone
registers with. The vendored REST spec's
`POST /api/fabric/resources/subscribers/{fabric_subscriber_id}/sip_endpoints`
requires exactly those two fields and takes `caller_id`, `send_as`, `ciphers`,
`codecs` and `encryption`. The subscriber itself is one
`POST /api/fabric/resources/subscribers` with an `email`, and
`GET /api/fabric/resources/{id}/addresses` lists its Fabric address. A SWML
`connect` whose `to` is that address sends a call to whatever registered with
the credential. The bundled schema lists a "Call Fabric Resource address" among
the forms `connect.to` takes.

Written against signalwire-sdk 3.0.1 (RestClient.fabric.subscribers,
SWMLService).
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

EMAIL = os.getenv("SUBSCRIBER_EMAIL", "workshop@ridgeline.example")
SIP_USERNAME = os.getenv("SIP_USERNAME", "workshop-desk")
CALLER_ID = os.getenv("SIP_CALLER_ID", "+15550001111")


def create_subscriber(email=EMAIL):
    """The person or desk, as a Fabric resource. Returns (resource id, address)."""
    resource = client.fabric.subscribers.create(email=email, display_name="Workshop desk")
    addresses = client.fabric.subscribers.list_addresses(resource["id"]).get("data", [])
    if not addresses:
        raise RuntimeError(f"subscriber {resource['id']} listed no address")
    return resource["id"], addresses[0]["name"]


def add_sip_credential(subscriber_id, username=SIP_USERNAME, caller_id=CALLER_ID):
    """What the softphone registers with. `username` and `password` are the
    spec's two required fields; the password is read from the environment here
    and is not a parameter, so no caller can pass one in."""
    password = os.getenv("SIP_PASSWORD")
    if not password:
        raise SystemExit("SIP_PASSWORD is required; see .env.example")
    return client.fabric.subscribers.create_sip_endpoint(
        subscriber_id, username=username, password=password, caller_id=caller_id)


def ring(address, service=None):
    """The document a number runs to ring the registered softphone."""
    service = service or SWMLService(name="ring", route="/ring")
    service.add_verb("answer", {})
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
    elif len(sys.argv) == 3 and sys.argv[1] == "credential":
        print(add_sip_credential(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "document":
        print(json.dumps(ring(sys.argv[2]).get_document(), indent=2))
    else:
        raise SystemExit("usage: python app.py subscriber | credential <subscriber_id> | "
                         "document <address>")
