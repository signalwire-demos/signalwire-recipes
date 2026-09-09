"""Send DTMF to an external IVR.

The digits travel with the origination, not as a verb after `connect`.

`connect` owns the bridge until the far leg ends, so a `send_digits` placed
after it does not run until the IVR has already hung up. The `dial` command
takes a `send_digits` parameter instead, described as digits to send *after the
call is answered*, which is the moment a phone tree starts listening.

Its pacing characters differ from the `send_digits` verb: here `w` is a wait
and `,` is a pause, and there is no capital `W`.

Written against signalwire-sdk 3.0.1 (RestClient.calling).
"""
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
IVR = os.getenv("IVR_NUMBER", "+15550100050")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

# (pauses to wait before pressing, key). One `,` is the documented pause unit;
# how long the far end talks before it will accept input decides the count.
ROUTE = [(6, "2"), (3, "1")]

# Allowed by the dial parameter: 0-9, A-D, *, #, w (wait), `,` (pause).
ALLOWED = set("0123456789ABCD*#w,")


def digits_for(route):
    """Waits before each key, spelled the way the parameter spells them."""
    out = "".join("," * pauses + key for pauses, key in route)
    bad = set(out) - ALLOWED
    if bad:
        raise ValueError(f"not sendable as DTMF: {sorted(bad)}")
    return out


def navigate(after_answer):
    """Dial the tree, press through it, then run `after_answer`."""
    return client.calling.dial(**{
        "from": FROM,
        "to": IVR,
        # pressed once the far end answers, which is when a menu listens
        "send_digits": digits_for(ROUTE),
        # what the call does once it is through the tree
        "swml": after_answer,
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["answered", "ended"],
    })


def hold_for_a_human():
    """The document that runs on our side once the digits are sent."""
    return {
        "version": "1.0.0",
        "sections": {
            "main": [
                {"answer": {}},
                # a human on the far end will eventually say something
                {"play": {"url": "silence:3600"}},
            ]
        },
    }


if __name__ == "__main__":
    print(navigate(hold_for_a_human()))
