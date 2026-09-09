"""Buy a number and point it at your app.

Three REST calls: search available numbers by area code or pattern, purchase
one, and set its call handler to your SWML URL. After the third call, dialling
the number fetches your document.

Written against signalwire-sdk 3.0.1 (RestClient.phone_numbers).

    python app.py search 415            # list candidates
    python app.py buy +14155550123 https://your-host/ivr
"""
import os
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()


def find(areacode=None, contains=None, number_type="local", max_results=5):
    """Search inventory. Returns the list of candidate numbers (E.164)."""
    params = {"number_type": number_type, "max_results": max_results}
    if areacode:
        params["areacode"] = areacode
    if contains:
        params["contains"] = contains
    res = client.phone_numbers.search(**params)
    return [n.get("e164") or n.get("number") for n in res.get("data", [])]


def buy(number):
    """Purchase a number. Returns the phone number resource (id, number, ...)."""
    return client.phone_numbers.create(number=number)


def point_at(number_id, swml_url, name=None):
    """Route inbound calls on the number to a SWML document at swml_url."""
    body = {"call_handler": "relay_script", "call_relay_script_url": swml_url}
    if name:
        body["name"] = name
    return client.phone_numbers.update(number_id, **body)


def provision(areacode, swml_url, name="recipes"):
    """Search -> buy the first candidate -> point it at swml_url."""
    candidates = find(areacode=areacode)
    if not candidates:
        raise SystemExit(f"no numbers available in {areacode}")
    bought = buy(candidates[0])
    point_at(bought["id"], swml_url, name=name)
    return bought


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["search", os.getenv("AREACODE", "415")]
    if cmd == "search":
        for n in find(areacode=rest[0]):
            print(n)
    elif cmd == "buy":
        number, url = rest
        bought = buy(number)
        point_at(bought["id"], url)
        print(f"{bought['number']} -> {url}")
    elif cmd == "provision":
        areacode, url = rest
        print(provision(areacode, url))
