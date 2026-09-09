"""Collect speech input and branch on it.

`prompt` asks a question and waits. What it listens for depends on which
parameters are set: speech detection turns on only when a speech parameter is
present, and digit detection turns on only when a digit parameter is. Set just
the speech ones and the keypad stays disarmed.

What the caller said arrives in `prompt_value`. `prompt_result` is the status
of the attempt, not its content, so the branch reads the first.

There is no AI agent here. A recogniser matches against hints and a `switch`
picks the section.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

# Destination per recognised phrase. Two phrases reach billing, which is the
# reason this is a table rather than three lines of YAML.
ROUTES = {
    "sales": ("sales", os.getenv("SALES_NUMBER", "+15550100001")),
    "support": ("support", os.getenv("SUPPORT_NUMBER", "+15550100002")),
    "account": ("billing", os.getenv("BILLING_NUMBER", "+15550100003")),
    "billing": ("billing", os.getenv("BILLING_NUMBER", "+15550100003")),
}

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="menu", route="/menu")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("prompt", {
        "play": "say:Are you calling about sales, support, or your account?",
        # speech parameters only, so digit collection stays off
        "speech_timeout": 12,
        "speech_end_timeout": 1.5,
        "speech_language": "en-US",
        "speech_hints": sorted(ROUTES),
    })
    service.add_verb("switch", {
        # what the caller said, not whether the attempt succeeded
        "variable": "prompt_value",
        "case": {
            phrase: [{"transfer": {"dest": section}}]
            for phrase, (section, _) in ROUTES.items()
        },
        "default": [
            {"play": {"url": "say:Sorry, I did not catch that."}},
            {"transfer": {"dest": "main"}},
        ],
    })
    for section, number in {v for v in ROUTES.values()}:
        service.add_section(section)
        service.add_verb_to_section(section, "play", {
            "url": f"say:Connecting you to {section}."})
        service.add_verb_to_section(section, "connect", {"to": number})
        service.add_verb_to_section(section, "hangup", {})
    return service


@app.route("/menu", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
