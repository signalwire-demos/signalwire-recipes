"""Detect an answering machine before your logic runs.

`detect_machine` classifies who picked up. The outcome lands in the
`detect_result` variable and is also POSTed to `status_url`, so the document
can branch on it without your code being involved.

`detect_message_end: true` is what makes a voicemail usable: detection holds
until the greeting finishes, so the message is left after the beep rather than
over the top of "please leave a message".

The document is placed with the call, so classification happens on the leg
being answered rather than on a call you have to bridge first.

Written against signalwire-sdk 3.0.1 (RestClient.calling).
"""
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

# Documented detect_result values, lowercase.
HUMAN, MACHINE, FAX = "human", "machine", "fax"
UNKNOWN = ("unknown", "detecting", "error")

MESSAGE = "This is Ridgeline Cycles. Your repair is ready for collection."


def reminder_document():
    """Classify first, then say the right thing to whoever answered."""
    return {
        "version": "1.0.0",
        "sections": {
            "main": [
                {"answer": {}},
                {"detect_machine": {
                    "detectors": "amd,fax",
                    # hold until the greeting ends, so the message lands
                    # after the beep instead of over it
                    "detect_message_end": True,
                    "initial_timeout": 4.5,
                    "end_silence_timeout": 1.0,
                    "status_url": f"{PUBLIC_URL}/amd-status",
                }},
                {"switch": {
                    "variable": "detect_result",
                    "case": {
                        HUMAN: [
                            # A person can be told something a machine
                            # cannot act on. Nothing here collects a digit,
                            # so nothing here offers one.
                            {"play": {"url": f"say:{MESSAGE} The workshop is "
                                             "open until six today."}},
                        ],
                        MACHINE: [
                            # detect_message_end held us until the beep
                            {"play": {"url": f"say:{MESSAGE}"}},
                        ],
                        FAX: [
                            # nothing to say to a fax tone
                            {"hangup": {}},
                        ],
                    },
                    # unknown, detecting and error land here. The message
                    # alone is the safe thing to play when the classifier
                    # could not decide: it works read to either.
                    "default": [
                        {"play": {"url": f"say:{MESSAGE}"}},
                    ],
                }},
                {"hangup": {}},
            ]
        },
    }


def call(to):
    return client.calling.dial(**{
        "from": FROM,
        "to": to,
        "swml": reminder_document(),
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["answered", "ended"],
    })


if __name__ == "__main__":
    import sys

    print(call(sys.argv[1] if len(sys.argv) > 1 else "+15552223333"))
