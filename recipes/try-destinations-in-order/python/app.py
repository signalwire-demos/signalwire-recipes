"""Try destinations in order.

`connect` takes a `serial` list of destinations to dial in order, or a
`parallel` list to dial at once, per the connect reference. When the bridge
ends, `result` runs against `connect_result`, which is "connected" or
"failed", and `connect_failed_reason` carries the detail.

The `to` field accepts phone numbers, SIP URIs and Resource addresses; this
list mixes the first two.

Written against signalwire-sdk 3.0.1 (SWMLService).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

# Comma-separated, tried in this order.
DESTINATIONS = [d.strip() for d in os.getenv(
    "DESTINATIONS", "+15550100001,sip:workshop@pbx.example.com,+15550100003"
).split(",") if d.strip()]
RING_SECONDS = int(os.getenv("RING_SECONDS", "15"))

GOODBYE = "say:Thanks for calling Ridgeline Cycles. Goodbye."
NOBODY = "say:Nobody could take your call. Please try again later."


def build(service=None):
    service = service or SWMLService(name="hunt", route="/hunt")
    service.reset_document()

    service.add_verb("answer", {})
    service.add_verb("play", {"url": "say:One moment while I find someone to help you."})
    service.add_verb("connect", {
        "timeout": RING_SECONDS,
        "serial": [{"to": d} for d in DESTINATIONS],
        "result": {"case": {
            "connected": [{"play": {"url": GOODBYE}}, {"hangup": {}}],
            "failed": [{"play": {"url": NOBODY}}, {"hangup": {}}],
        }},
    })

    # Variant: dial every phone destination at once; SIP entries are left out.
    service.add_section("parallel")
    service.add_verb_to_section("parallel", "answer", {})
    service.add_verb_to_section("parallel", "connect", {
        "timeout": RING_SECONDS + 5,
        "parallel": [{"to": d} for d in DESTINATIONS if not d.startswith("sip:")],
        "result": {"case": {
            "failed": [{"play": {"url": "say:Nobody could take your call."}},
                       {"hangup": {}}],
        }},
    })
    service.add_verb_to_section("parallel", "hangup", {})
    return service


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
