"""Pause a voice AI agent mid-call and bring it back.

`calling.ai_hold` puts the caller on hold and stops the agent listening;
`calling.ai_unhold` brings it back; `calling.ai.stop` ends the AI on the call
and leaves the call itself up. Each is one POST to /api/calling/calls addressed
to the call id.

The spec is explicit that `ai_hold`'s `timeout` is a numeric string, and that
an integer payload is rejected, so this converts it and refuses anything that
is not a whole number of seconds.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py hold <call_id> [seconds]
    python app.py unhold <call_id>
    python app.py stop <call_id>
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# what the agent says before the hold music starts
HOLD_PROMPT = "Let me check that for you. One moment."


def hold(call_id, seconds=90, prompt=HOLD_PROMPT):
    """Hold the caller for `seconds`, after the agent says `prompt`."""
    if int(seconds) != float(seconds):
        raise ValueError(f"seconds must be a whole number, not {seconds!r}")
    # the spec: a numeric string. An integer payload is rejected
    return client.calling.ai_hold(call_id, timeout=str(int(seconds)), prompt=prompt)


def unhold(call_id):
    """Take the caller off hold. The agent is listening again."""
    return client.calling.ai_unhold(call_id)


def stop(call_id):
    """End the AI on this call. The call itself stays up."""
    # the method is ai_stop; the command on the wire is calling.ai.stop
    return client.calling.ai_stop(call_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    if not call_id:
        print(__doc__)
    elif cmd == "hold":
        print(hold(call_id, *(int(x) for x in rest)))
    elif cmd == "unhold":
        print(unhold(call_id))
    elif cmd == "stop":
        print(stop(call_id))
    else:
        print(__doc__)
