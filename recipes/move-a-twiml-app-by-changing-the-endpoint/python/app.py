"""Move a TwiML app by changing the endpoint.

The compatibility API page (https://signalwire.com/docs/compatibility-api)
says to "update the base URL from api.twilio.com to your-space.signalwire.com"
and that "Your existing TwiML/cXML response handlers work without
modification." The SDK's compat client does the first part. Every request goes
to `/api/laml/2010-04-01/Accounts/<project id>/...` on your Space. Your project
id is the account and your API token is the password. The second part is this
Flask handler, a TwiML document served as cXML with nothing changed but the
name.

Written against signalwire-sdk 3.0.1 (RestClient.compat.calls) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, Response
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

FROM = os.getenv("CALL_FROM")
VOICE_URL = os.getenv("VOICE_URL")
for name, value in (("CALL_FROM", FROM), ("VOICE_URL", VOICE_URL)):
    if not value:
        raise SystemExit(f"{name} is required; see .env.example")

GREETING = "Thanks for calling Ridgeline Cycles. The workshop opens at nine."

# the handler a Twilio app would have: the same verbs, the same shape
CXML = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        "  <Say voice=\"Polly.Salli\">{greeting}</Say>\n"
        "  <Hangup/>\n"
        "</Response>\n")


def place(to):
    """Create a call the way the Twilio-shaped code did: To, From and the URL
    of the handler. Only the client's base URL and credentials changed."""
    return client.compat.calls.create(To=to, From=FROM, Url=VOICE_URL)


app = Flask(__name__)


@app.post("/voice")
def voice():
    return Response(CXML.format(greeting=GREETING), mimetype="text/xml")


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        print(place(sys.argv[1]))
    else:
        app.run(port=int(os.getenv("PORT", "8080")))
