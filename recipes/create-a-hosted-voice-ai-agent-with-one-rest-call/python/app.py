"""Create a hosted voice AI agent with one REST call.

The agent you would serve from your own host is the agent SignalWire can host
for you. `AgentBase` renders the `ai` verb; its `prompt`, `params` and
`post_prompt` are exactly the fields `POST /api/fabric/resources/ai_agents`
takes, and the spec points at the SWML `ai` reference for each. One more POST
puts a phone number on the resource. No server of yours stays running.

Written against signalwire-sdk 3.0.1 (AgentBase, RestClient.fabric).

    python app.py create                  # the hosted agent, printed with its id
    python app.py point <agent_id> +15551230000
"""
import json
import sys

from dotenv import load_dotenv
from signalwire import AgentBase
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

NAME = "ridgeline-front-desk"


class FrontDesk(AgentBase):
    """The same definition you would run yourself, rendered rather than served."""

    def __init__(self):
        super().__init__(name=NAME, route="/front-desk")
        self.prompt_add_section("Role", "You answer the phone for Ridgeline Cycles, "
                                        "a bike shop. Be brief and warm.")
        self.prompt_add_section("Hours", "Open Monday to Friday, nine to five, "
                                         "Eastern time. Closed weekends.")
        self.prompt_add_section("Limits", "You cannot book repairs. Offer the shop "
                                          "number for that and end the call kindly.")
        self.set_post_prompt("Summarise the call in one sentence.")
        self.set_params({"end_of_speech_timeout": 700})


def definition(agent=None):
    """The `ai` verb the agent renders, which is what the hosted resource needs."""
    agent = agent or FrontDesk()
    doc = agent._render_swml()
    if isinstance(doc, str):  # 3.0.1 renders the document as a JSON string
        doc = json.loads(doc)
    (ai,) = [step["ai"] for step in doc["sections"]["main"] if "ai" in step]
    body = {"name": NAME, "prompt": ai["prompt"]}
    for key in ("params", "post_prompt"):
        if key in ai:
            body[key] = ai[key]
    return body


def create():
    """One POST. The response carries the resource id a number can point at."""
    return client.fabric.ai_agents.create(**definition())


def number_id(e164):
    """`filter_number` is a contains match, so compare the number exactly."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number in this project")


def point_number(resource_id, e164):
    """Route inbound calls on the number to the hosted agent."""
    return client.fabric.resources.assign_phone_route(
        resource_id, phone_route_id=number_id(e164), handler="calling")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["create"]:
        made = create()
        print(made.get("id"), made.get("display_name"))
    elif len(args) == 3 and args[0] == "point":
        print(point_number(args[1], args[2]))
    else:
        print(__doc__)
