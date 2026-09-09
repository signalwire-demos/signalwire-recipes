"""Redact a message body after sending.

One PATCH clears the stored body of a message in SignalWire's records. The
spec allows exactly one value, an empty string, and the platform rejects
anything else with `body_must_be_empty`. The message id is the segment id the
send returned, the same id `/api/messaging/logs` shows. The platform redacts
only a message in a terminal state, delivered, undelivered or failed; it
refuses queued and initiated.

The SDK's REST client has no wrapper for this path in 3.0.1, so the request
goes through the HTTP client the namespaces share.

Written against signalwire-sdk 3.0.1 (RestClient).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

# the client's HTTP layer, shared by every namespace; used directly because
# 3.0.1 wraps no method for the messaging redact path
http = client._http


def redact(message_id):
    """Clear the body. The spec accepts only "" here."""
    return http.patch(f"/api/messaging/messages/{message_id}", body={"body": ""})


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: python app.py <message_id>")
    print(redact(sys.argv[1]))
