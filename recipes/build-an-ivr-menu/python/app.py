"""Build an IVR menu.

The same document as swml/agent.yaml, built in Python so the destinations come
from the environment and every verb is validated against the SWML schema before
it is served.

Written against signalwire-sdk 3.0.1 (SWMLService).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

SALES = os.getenv("SALES_NUMBER", "+15550100001")
SUPPORT = os.getenv("SUPPORT_NUMBER", "+15550100002")
HOURS = "We are open Monday to Friday, nine to five, Eastern time."

MENU = {
    "1": ("sales", "Connecting you to sales.", SALES),
    "2": ("support", "Connecting you to support.", SUPPORT),
}


def build(service=None):
    """Populate a SWMLService with the menu. Returns the service."""
    service = service or SWMLService(name="ivr", route="/ivr")
    service.reset_document()

    service.add_verb("answer", {})
    service.add_verb("prompt", {
        "play": "say:Thanks for calling. Press 1 for sales, 2 for support, "
                "or 3 for opening hours.",
        "max_digits": 1,
        "digit_timeout": 6,
        "initial_timeout": 8,
    })
    cases = {digit: [{"transfer": {"dest": section}}]
             for digit, (section, _, _) in MENU.items()}
    cases["3"] = [{"transfer": {"dest": "hours"}}]
    service.add_verb("switch", {
        "variable": "prompt_value",
        "case": cases,
        "default": [
            {"play": {"url": "say:Sorry, I did not catch that."}},
            {"transfer": {"dest": "main"}},
        ],
    })

    for section, announce, number in MENU.values():
        service.add_section(section)
        service.add_verb_to_section(section, "play", {"url": f"say:{announce}"})
        service.add_verb_to_section(section, "connect", {"to": number})
        service.add_verb_to_section(section, "hangup", {})

    service.add_section("hours")
    service.add_verb_to_section("hours", "play", {"url": f"say:{HOURS}"})
    service.add_verb_to_section("hours", "hangup", {})
    return service


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
