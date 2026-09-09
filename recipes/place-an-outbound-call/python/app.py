"""Place an outbound call and hand it a document.

One POST originates the call. The same request carries the SWML the call runs
once someone answers, so there is no second fetch and no URL to host.

`dial` takes either `url` or `swml`. `url` makes the platform fetch a document
from you when the call connects; `swml` puts the document in the request. This
recipe uses `swml`, because a reminder call has nothing to look up.

Written against signalwire-sdk 3.0.1 (RestClient.calling).
"""
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment when not passed explicitly.
client = RestClient()

FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")


def reminder_document(message):
    """The document the call runs when it is answered."""
    return {
        "version": "1.0.0",
        "sections": {
            "main": [
                {"answer": {}},
                {"play": {"url": f"say:{message}"}},
                {"hangup": {}},
            ]
        },
    }


def place(to, message):
    """Originate the call. `from` is a Python keyword, so it goes in a dict."""
    return client.calling.dial(**{
        "from": FROM,
        "to": to,
        "swml": reminder_document(message),
        # where the lifecycle is reported; see handle-call-status-callbacks
        "status_url": f"{PUBLIC_URL}/call-status",
        "status_events": ["ringing", "answered", "ended"],
        # stop ringing rather than rolling to the callee's voicemail
        "timeout": 25,
    })


if __name__ == "__main__":
    import sys

    to = sys.argv[1] if len(sys.argv) > 1 else "+15552223333"
    result = place(to, "This is a reminder that your bike is ready for pickup.")
    print(result)
