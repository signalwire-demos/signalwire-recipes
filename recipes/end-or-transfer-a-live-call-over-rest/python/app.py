"""End or transfer a live call over REST.

Three call commands, each one POST to /api/calling/calls addressed to a call id:
`calling.end` hangs up with a reason, `calling.transfer` moves the call to a new
destination, and `calling.disconnect` unbridges two connected calls.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py end <call_id> [reason]
    python app.py transfer <call_id> <dest>
    python app.py disconnect <call_id>
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# the spec's enum for calling.end; anything else is refused before it is sent
END_REASONS = ("hangup", "cancel", "busy", "noAnswer", "decline", "error")


def hang_up(call_id, reason="hangup"):
    """End the call. `reason` is what the far end and the logs see."""
    if reason not in END_REASONS:
        raise ValueError(f"reason must be one of {END_REASONS}, not {reason!r}")
    return client.calling.end(call_id, reason=reason)


def transfer(call_id, dest):
    """Send the call somewhere else: a phone number, a SIP URI or a SWML URL."""
    return client.calling.transfer(call_id, dest=dest)


def unbridge(call_id):
    """Separate this call from its peer. The spec hangs up neither leg."""
    return client.calling.disconnect(call_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    if not call_id:
        print(__doc__)
    elif cmd == "end":
        print(hang_up(call_id, *rest))
    elif cmd == "transfer":
        print(transfer(call_id, rest[0]))
    elif cmd == "disconnect":
        print(unbridge(call_id))
    else:
        print(__doc__)
