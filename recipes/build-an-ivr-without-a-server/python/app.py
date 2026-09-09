"""Build an IVR without a server.

A call flow is a SWML document you hand to the platform. The vendored REST
spec describes `relayml` as "The calling SWML document this Call Flow should
execute", so no server of yours serves it. `POST /api/fabric/resources/call_flows`
requires a `title`. The response is a Fabric resource with an `id`.
`POST /api/fabric/resources/{id}/phone_routes` then points a number at it; the
spec requires `phone_route_id` and `handler`, and `calling` is the handler for
voice.

You build the document with `SWMLService`, whose `add_verb` raises
`SchemaValidationError` on a verb the bundled schema rejects. The verbs are
answer, a `prompt` for one digit, a `switch` on `prompt_value` with a `connect`
per desk, and a spoken fallback.

Written against signalwire-sdk 3.0.1 (SWMLService, RestClient.fabric).
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

DESKS = {"1": os.getenv("SALES_NUMBER", "+15550100001"),
         "2": os.getenv("WORKSHOP_NUMBER", "+15550100002")}
MENU = "Thanks for calling Ridgeline Cycles. Press 1 for sales, or 2 for the workshop."
FALLBACK = "Sorry, that was not an option. Goodbye."


def build(service=None):
    """The IVR as a SWML document, validated verb by verb."""
    service = service or SWMLService(name="ivr", route="/ivr")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("prompt", {"play": f"say:{MENU}", "max_digits": 1,
                                "initial_timeout": 8})
    service.add_verb("switch", {
        "variable": "prompt_value",
        "case": {digit: [{"connect": {"to": number, "timeout": 25}}]
                 for digit, number in DESKS.items()},
        "default": [{"play": {"url": f"say:{FALLBACK}"}}],
    })
    service.add_verb("hangup", {})
    return service


# The spec pairs relayml with flow_data: provide both or omit both. flow_data is
# the Call Flow Builder's canvas state and is opaque to the API, so a flow
# authored in code sends a small descriptor rather than a canvas.
FLOW_DATA = {"generated_by": "signalwire-recipes",
             "recipe": "build-an-ivr-without-a-server"}


def deploy(title="Ridgeline Cycles IVR"):
    """Create the call flow from the document. Returns the resource."""
    return client.fabric.call_flows.create(
        title=title, relayml=build().get_document(), flow_data=FLOW_DATA)


def number_id(e164):
    """The resource id of a number on your project, by exact match."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number on this project")


def point_number(resource_id, e164):
    """Route a number's calls to the call flow."""
    return client.fabric.resources.assign_phone_route(
        resource_id, phone_route_id=number_id(e164), handler="calling")


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "document":
        print(json.dumps(build().get_document(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == "deploy":
        print(deploy())
    elif len(sys.argv) == 4 and sys.argv[1] == "point":
        print(point_number(sys.argv[2], sys.argv[3]))
    else:
        raise SystemExit("usage: python app.py document | deploy | "
                         "point <resource_id> <+1number>")
