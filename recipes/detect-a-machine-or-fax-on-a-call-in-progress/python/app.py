"""Detect a machine, fax tone or digits on a call in progress.

`calling.detect` starts detection on a call that is already up, from outside
the call's document. The `detect` object picks what to listen for: `machine`,
`fax` or `digit`. The result arrives at your `status_url`, so a detect without
one is refused here before it is sent. `calling.detect.stop` gives up early.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py machine <call_id> <status_url>
    python app.py fax <call_id> <status_url>
    python app.py digits <call_id> <status_url>
    python app.py stop <call_id>
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# one id names this detection, and stop names it again
CONTROL_ID = "screening"

# the spec's three detection types
TYPES = ("machine", "fax", "digit")


def _needs_status_url(status_url):
    # the result arrives only by webhook; without one the detect is unobservable
    if not status_url:
        raise ValueError("a detect needs a status_url to deliver its result")


def machine(call_id, status_url, timeout=30, control_id=CONTROL_ID):
    """Answering machine detection, with the thresholds spelled out."""
    _needs_status_url(status_url)
    params = {"machine_voice_threshold": 1.25, "machine_words_threshold": 6,
              "detect_message_end": True}
    detect = {"type": "machine", "params": params}
    return client.calling.detect(call_id, control_id=control_id, detect=detect,
                                 timeout=timeout, status_url=status_url)


def fax(call_id, status_url, tone="CED", timeout=30, control_id=CONTROL_ID):
    """Fax tone detection. CED is the answering tone, CNG the calling tone."""
    _needs_status_url(status_url)
    detect = {"type": "fax", "params": {"tone": tone}}
    return client.calling.detect(call_id, control_id=control_id, detect=detect,
                                 timeout=timeout, status_url=status_url)


def digits(call_id, status_url, wanted="0123456789", timeout=30, control_id=CONTROL_ID):
    """DTMF detection: report when any of these digits is pressed."""
    _needs_status_url(status_url)
    detect = {"type": "digit", "params": {"digits": wanted}}
    return client.calling.detect(call_id, control_id=control_id, detect=detect,
                                 timeout=timeout, status_url=status_url)


def stop(call_id, control_id=CONTROL_ID):
    """Give up on the detection before its timeout."""
    return client.calling.detect_stop(call_id, control_id=control_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    actions = {"machine": machine, "fax": fax, "digits": digits, "stop": stop}
    if not call_id or cmd not in actions:
        print(__doc__)
    else:
        print(actions[cmd](call_id, *rest))
