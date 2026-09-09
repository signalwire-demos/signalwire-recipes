"""Verify a caller ID for outbound calls.

A number you own elsewhere becomes a permitted outbound caller ID in three
REST calls. `create` registers the number and starts a verification call to
it; the person who answers hears a code. `submit_verification` sends that code
back. `redial_verification` places the call again if the code was missed.

Written against signalwire-sdk 3.0.1 (RestClient.verified_callers).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def start(number, name):
    """Register the number; the platform calls it and reads out a code."""
    return client.verified_callers.create(number=number, name=name)


def confirm(caller_id, code):
    """Send back the code the person who answered heard."""
    return client.verified_callers.submit_verification(caller_id,
                                                       verification_code=code)


def resend(caller_id):
    """Place the verification call again."""
    return client.verified_callers.redial_verification(caller_id)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python app.py start +1XXXXXXXXXX 'Shop mobile'\n"
                         "       python app.py confirm <id> <code>\n"
                         "       python app.py resend <id>")
    verb, args = sys.argv[1], sys.argv[2:]
    print({"start": start, "confirm": confirm, "resend": resend}[verb](*args))
