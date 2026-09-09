"""Pause and resume a call recording over REST.

Four call commands share one `control_id`: `calling.record` starts a recording
on a live call, `calling.record.pause` and `calling.record.resume` bracket the
part you must not keep, and `calling.record.stop` ends it. Each is one POST to
/api/calling/calls addressed to the call id.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py start <call_id> [status_url]
    python app.py pause <call_id>
    python app.py resume <call_id>
    python app.py stop <call_id>
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# one id names the recording across start, pause, resume and stop
CONTROL_ID = "agent-desk-recording"

# how the pause reads in the file: `skip` cuts it out, `silence` keeps the timing
PAUSE_BEHAVIOR = "silence"


# The REST defaults are prompt-style: stop after 4s without speech, after 0.5s
# of silence, or on `#`. SWML's whole-call verb, record_call, defaults these
# three to 0, 0 and "", and a call recording wants those.
WHOLE_CALL = {"initial_timeout": 0, "end_silence_timeout": 0, "terminators": ""}


def start(call_id, status_url=None, control_id=CONTROL_ID):
    """Record both directions to one stereo mp3, for as long as the call runs."""
    audio = {"stereo": True, "direction": "both", "format": "mp3", "max_length": 0,
             **WHOLE_CALL}
    params = {"control_id": control_id, "record": {"audio": audio}}
    if status_url:
        # the recording URL arrives here when the recording finishes
        params["status_url"] = status_url
    return client.calling.record(call_id, **params)


def pause(call_id, control_id=CONTROL_ID, behavior=PAUSE_BEHAVIOR):
    """Stop capturing. The file keeps the gap as silence, or drops it with `skip`."""
    return client.calling.record_pause(call_id, control_id=control_id, behavior=behavior)


def resume(call_id, control_id=CONTROL_ID):
    """Capture again, into the same file."""
    return client.calling.record_resume(call_id, control_id=control_id)


def stop(call_id, control_id=CONTROL_ID):
    """Finish the recording. The status_url from `start` gets the final URL."""
    return client.calling.record_stop(call_id, control_id=control_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    actions = {"start": start, "pause": pause, "resume": resume, "stop": stop}
    if cmd in actions and call_id:
        print(actions[cmd](call_id, *rest))
    else:
        print(__doc__)
