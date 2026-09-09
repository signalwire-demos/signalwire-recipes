"""Send a batch within your rate limit.

The rate limits page (https://signalwire.com/docs/platform/rate-limits) gives
messaging throughput per number type: "4 MPS" for 10DLC, "3 messages per
second (MPS)" for toll-free, "10 MPS" for short codes, and a backlog of
"10,000 queued messages". Past the rate, SignalWire queues messages in the
order received. Once the backlog is full, "SignalWire will stop adding to the
Messaging queue". So a batch that sends faster than its number's rate is not
faster, it is queued, and a burst that fills the queue loses what did not fit.

This pacer sends one message per interval for the number type, so the queue
never builds. The clock and the sleep are arguments, so the verifier can run
it in no time at all.

Written against signalwire-sdk 3.0.1 (RestClient). The 3.0.1 client has no
messaging namespace, so the send goes through the HTTP client every namespace
shares.
"""
import os
import time

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()
http = client._http

FROM = os.getenv("SMS_FROM")
if not FROM:
    raise SystemExit("SMS_FROM is required: the purchased number the batch goes out from")
NUMBER_TYPE = os.getenv("NUMBER_TYPE", "10dlc")

# messages per second, from the rate limits page
LIMITS = {"10dlc": 4, "toll-free": 3, "short-code": 10}


def send_batch(recipients, body, number_type=NUMBER_TYPE,
               clock=time.monotonic, sleep=time.sleep):
    """One message per recipient, no faster than the number type's rate.

    Returns the platform's response for each message, in order."""
    if number_type not in LIMITS:
        raise ValueError(f"number_type must be one of {sorted(LIMITS)}, "
                         f"not {number_type!r}")
    interval = 1 / LIMITS[number_type]
    results = []
    next_at = clock()
    for to in recipients:
        now = clock()
        if now < next_at:
            sleep(next_at - now)
            now = clock()  # a sleep can overshoot; pace from when it woke
        results.append(http.post("/api/messaging/messages",
                                 body={"to": to, "from": FROM, "body": body}))
        next_at = max(now, next_at) + interval
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise SystemExit("usage: python app.py <body> <+1number> [+1number ...]")
    for sent in send_batch(sys.argv[2:], sys.argv[1]):
        print(sent.get("id"), sent.get("to"), sent.get("status"))
