"""Transfer a SIP call with REFER.

The spec's command table describes `calling.refer` as "Transfer a SIP call via
SIP REFER". The command takes a `device`, and the device takes a `type` of
`sip`, the only value the enum holds, and `params` whose `to` must be a `sip:`
URI. Optional credentials go with it when the far end challenges the REFER.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py refer <call_id> sip:desk-2@pbx.example.com
"""
import os
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# the only device type the spec's enum holds
DEVICE_TYPE = "sip"

# credentials for a far end that challenges the REFER
SIP_USERNAME = os.getenv("SIP_REFER_USERNAME", "")
SIP_PASSWORD = os.getenv("SIP_REFER_PASSWORD", "")


def _sip_uri(value, field):
    if not value.startswith("sip:"):
        raise ValueError(f"{field} must be a sip: URI, not {value!r}")
    return value


def refer(call_id, to, from_uri=None, status_url=None):
    """Ask the far SIP end to transfer the call to `to`."""
    params = {"to": _sip_uri(to, "to")}
    if from_uri:
        # the spec: optional, and a sip: URI when it is there
        params["from"] = _sip_uri(from_uri, "from")
    if SIP_USERNAME and SIP_PASSWORD:
        params["username"] = SIP_USERNAME
        params["password"] = SIP_PASSWORD
    body = {"device": {"type": DEVICE_TYPE, "params": params}}
    if status_url:
        # refer lifecycle webhooks land here
        body["status_url"] = status_url
    return client.calling.refer(call_id, **body)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    if not call_id or cmd != "refer":
        print(__doc__)
    else:
        print(refer(call_id, *rest))
