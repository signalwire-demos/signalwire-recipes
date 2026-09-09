"""Check consent before an outbound call.

The platform mechanism here is thin on purpose: one `dial`. The recipe is the
ordering around it. `place()` looks the number up in your consent store and
checks the local clock at the callee's zone before it calls
`client.calling.dial`. No record, a withdrawn record, or a time outside the
window, and the code builds no request at all. The decision is code, and it
runs before the dial.

Written against signalwire-sdk 3.0.1 (RestClient.calling).
"""
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()
FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")

# Your consent store: number -> consented flag and time zone. Yours will carry
# whatever your counsel says a consent record must hold.
CONSENT = {
    "+15557654321": {"consented": True, "tz": "America/Los_Angeles"},
    "+15550009999": {"consented": False, "tz": "America/New_York"},
}

# The permitted calling window, in the callee's local time.
WINDOW = (time(9, 0), time(20, 0))


class NoConsent(Exception):
    """Raised instead of dialling. The message says which check failed."""


def allowed(number, now=None):
    """The decision. Returns None when the call may go ahead, else a reason.
    `now` is for tests and must carry a zone. A naive clock would read in the
    server's zone, which is the mistake this recipe exists to avoid."""
    if now is not None and now.utcoffset() is None:
        raise ValueError("now must carry a time zone")
    record = CONSENT.get(number)
    if not record:
        return "no consent on record"
    if not record["consented"]:
        return "consent withdrawn"
    local = (now or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(record["tz"]))
    if not WINDOW[0] <= local.time() <= WINDOW[1]:
        return f"outside the calling window, it is {local:%H:%M} in {record['tz']}"
    return None


def place(number, message, now=None):
    """Dial only after the checks pass. The dial is the last thing here."""
    reason = allowed(number, now)
    if reason:
        raise NoConsent(f"not calling {number}: {reason}")
    return client.calling.dial(**{
        "from": FROM, "to": number, "timeout": 25,
        "swml": {"version": "1.0.0", "sections": {"main": [
            {"answer": {}}, {"play": {"url": f"say:{message}"}}, {"hangup": {}}]}},
    })


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2 or not sys.argv[1].startswith("+"):
        raise SystemExit("usage: python app.py +1XXXXXXXXXX")
    try:
        print(place(sys.argv[1], "This is Ridgeline Cycles. Your bike is ready."))
    except NoConsent as e:
        raise SystemExit(str(e))
