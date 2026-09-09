"""Transfer a call.

`connect` bridges the live call to a phone number, a SIP URI or a Resource
address. When the far end hangs up, execution continues with the verbs after
`connect` - the return path. Set transfer_after_bridge to make it permanent.

Written against signalwire-sdk 3.0.1 (SWMLService).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

DEST = os.getenv("TRANSFER_TO", "+15550100001")
SIP_DEST = os.getenv("SIP_TRANSFER_TO", "sip:support@pbx.example.com")
PERMANENT = os.getenv("PERMANENT", "false").lower() == "true"


def build(service=None):
    service = service or SWMLService(name="transfer", route="/transfer")
    service.reset_document()

    service.add_verb("answer", {})
    service.add_verb("play", {"url": "say:Please hold while I connect you."})
    connect = {"to": DEST, "timeout": 20, "ringback": ["ring:us"]}
    if PERMANENT:
        connect["transfer_after_bridge"] = "true"
    service.add_verb("connect", connect)
    # Reached only when the bridge ends and the transfer was not permanent.
    service.add_verb("play", {
        "url": "say:The other party has left the call. Thank you for calling."})
    service.add_verb("hangup", {})

    # Variant: a SIP destination with custom headers on the INVITE.
    service.add_section("sip")
    service.add_verb_to_section("sip", "answer", {})
    service.add_verb_to_section("sip", "connect", {
        "to": SIP_DEST,
        "headers": [
            {"name": "X-Account-Id", "value": os.getenv("ACCOUNT_ID", "acct-1234")},
            {"name": "X-Source", "value": "signalwire-recipes"},
        ],
    })
    service.add_verb_to_section("sip", "hangup", {})
    return service


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
