"""Stream call audio to your own server.

`tap` sends a copy of the call's audio to a destination of yours. The bundled
schema gives it a `uri` of `rtp://IP:port`, `ws://` or `wss://` and a
`direction` of `speak`, `listen` or `both`. `codec` is PCMU or PCMA, and
`stop_tap` ends the tap by its `control_id`. Over REST the same operation is
the call command `calling.tap`, with a `device` of type `ws` or `rtp`.

Written against signalwire-sdk 3.0.1 (SWMLService, RestClient.calling).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

TAP_URI = os.getenv("TAP_URI", "wss://media.example.com/tap")
OWNER = os.getenv("OWNER_NUMBER", "+15550100001")
CONTROL_ID = "workshop-tap"


def build(service=None):
    """Fork both directions to your server for the length of the bridge."""
    service = service or SWMLService(name="tap", route="/tap")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("tap", {"uri": TAP_URI, "control_id": CONTROL_ID,
                             "direction": "both", "codec": "PCMU"})
    service.add_verb("connect", {"to": OWNER, "timeout": 20})
    service.add_verb("stop_tap", {"control_id": CONTROL_ID})
    service.add_verb("hangup", {})
    return service


def start_tap(call_id):
    """The same fork, started mid-call from your backend."""
    return client.calling.tap(call_id, control_id=CONTROL_ID,
                              tap={"type": "audio", "params": {"direction": "both"}},
                              device={"type": "ws", "params": {"uri": TAP_URI}})


def stop_tap(call_id):
    return client.calling.tap_stop(call_id, control_id=CONTROL_ID)


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
