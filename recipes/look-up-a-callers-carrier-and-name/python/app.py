"""Look up a caller's carrier and name.

One GET returns what the platform knows about a number: whether it is valid,
its formatted forms, its country and time zones. `include=carrier,cnam` adds
carrier details and the CNAM caller-ID name. The spec says the included
information is "some of which are billable".

Written against signalwire-sdk 3.0.1 (RestClient.lookup).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def enrich(e164):
    """Carrier and caller-ID name for a number, in one request."""
    return client.lookup.phone_number(e164, include="carrier,cnam")


def check(e164):
    """The base lookup, without requesting the carrier or CNAM extras."""
    return client.lookup.phone_number(e164)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2 or not sys.argv[1].startswith("+"):
        raise SystemExit("usage: python app.py +1XXXXXXXXXX")
    print(enrich(sys.argv[1]))
