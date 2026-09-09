"""Host a TwiML bin without a server.

A cXML document does not need a server of yours. One POST to
`/api/fabric/resources/cxml_scripts` with `display_name` and `contents` stores
it, and the response carries the `request_url` SignalWire serves it from. One
more POST puts a phone number on it. The compat twin is
`POST /Accounts/{AccountSid}/LamlBins` with `Name` and `Contents`.

Written against signalwire-sdk 3.0.1 (RestClient.fabric, RestClient.phone_numbers).

    python app.py create
    python app.py point <script_id> +15551230000
"""
import os
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

NAME = "workshop line"
FORWARD_TO = os.getenv("FORWARD_TO", "+15550100001")

# the whole application: a greeting and a forward, as TwiML
CONTENTS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '  <Say>Connecting you to the workshop.</Say>\n'
            '  <Dial timeout="20">{to}</Dial>\n'
            '</Response>\n')


def contents(forward_to=FORWARD_TO):
    return CONTENTS.format(to=forward_to)


def create():
    """One POST. The response carries the id and the URL SignalWire serves it from."""
    made = client.fabric.cxml_scripts.create(display_name=NAME, contents=contents())
    return made["id"], made["cxml_script"]["request_url"]


def number_id(e164):
    """`filter_number` is a contains match, so compare the number exactly."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number in this project")


def point_number(script_id, e164):
    """Route inbound calls on the number to the hosted script."""
    return client.fabric.resources.assign_phone_route(
        script_id, phone_route_id=number_id(e164), handler="calling")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["create"]:
        script_id, url = create()
        print(script_id, url)
    elif len(args) == 3 and args[0] == "point":
        print(point_number(args[1], args[2]))
    else:
        print("usage: python app.py create | python app.py point <script_id> <e164>")
