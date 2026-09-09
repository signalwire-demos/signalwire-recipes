"""Look up the caller and branch inside the call flow.

The call fetches the caller's record itself. `request` with `save_variables`
true parses your API's JSON into `request_response.<field>`; `switch` then
branches on one of those fields, and a `cond` around it sends the call to a
human when the lookup fails. The document is hosted as a Call Flow, so no
server of yours is in the call path.

Written against signalwire-sdk 3.0.1 (SWMLService, RestClient.fabric).

    python app.py deploy
    python app.py point <resource_id> +15551230000
"""
import os
import sys

from dotenv import load_dotenv
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# your system of record: the endpoint the call asks about the caller
CRM_URL = os.getenv("CRM_URL", "https://crm.example.com/lookup")
CRM_TOKEN = os.getenv("CRM_TOKEN", "replace-me")

# where each tier lands. An unknown tier is treated as standard.
DESKS = {"gold": os.getenv("GOLD_NUMBER", "+15550100001"),
         "standard": os.getenv("STANDARD_NUMBER", "+15550100002")}
APOLOGY = "One moment, I could not look up your account."

# The spec pairs relayml with flow_data: provide both or omit both.
FLOW_DATA = {"generated_by": "signalwire-recipes",
             "recipe": "look-up-the-caller-and-branch-inside-the-call-flow"}


def build(service=None):
    """The routing document, each verb validated as it is added."""
    service = service or SWMLService(name="crm-router", route="/router")
    service.reset_document()
    service.add_verb("answer", {})
    # %{call.from} is substituted at runtime; the schema accepts ${...} too
    service.add_verb("request", {
        "url": CRM_URL,
        "method": "POST",
        "headers": {"Content-Type": "application/json",
                    "Authorization": f"Bearer {CRM_TOKEN}"},
        "body": {"phone": "%{call.from}"},
        # without this the response is not parsed into request_response.<field>
        "save_variables": True,
        "connect_timeout": 3,
        "timeout": 5,
    })
    # cond takes an array and add_verb takes a dict, so this one is appended.
    # get_document() hands back the live document, so order is preserved.
    main = service.get_document()["sections"]["main"]
    main.append({"cond": [
        {"when": "request_result == 'success'",
         "then": [{"switch": {
             "variable": "request_response.tier",
             "case": {tier: [{"connect": {"to": number, "timeout": 25}}]
                      for tier, number in DESKS.items()},
             # a record with a tier you do not know is still a customer
             "default": [{"connect": {"to": DESKS["standard"], "timeout": 25}}],
         }}]},
        # the lookup failed or timed out: reach a human anyway
        {"else": [{"play": {"url": f"say:{APOLOGY}"}},
                  {"connect": {"to": DESKS["standard"], "timeout": 25}}]},
    ]})
    service.add_verb("hangup", {})
    return service


def deploy(title="Ridgeline Cycles router"):
    """Host the document as a Call Flow. Returns the resource."""
    return client.fabric.call_flows.create(
        title=title, relayml=build().get_document(), flow_data=FLOW_DATA)


def number_id(e164):
    """`filter_number` is a contains match, so compare the number exactly."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number on this project")


def point_number(resource_id, e164):
    """Route inbound calls on the number to the hosted flow."""
    return client.fabric.resources.assign_phone_route(
        resource_id, phone_route_id=number_id(e164), handler="calling")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["deploy"]:
        flow = deploy()
        print(flow["id"])
    elif len(args) == 3 and args[0] == "point":
        print(point_number(args[1], args[2]))
    else:
        print("usage: python app.py deploy | python app.py point <resource_id> <e164>")
