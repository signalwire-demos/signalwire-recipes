"""Stream call audio to a WebSocket that checks a bearer token.

`calling.stream` opens a WebSocket to your endpoint and sends the call's audio
down it. The spec requires `wss://`, so plain `ws://` is refused here before it
is sent. `authorization_bearer_token` becomes the `Authorization: Bearer`
header on the connection, `track` picks which side of the call to send, and
`custom_parameters` reach your endpoint as connection metadata.
`calling.stream.stop` ends it by control id.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py start <call_id> wss://media.example.com/calls
    python app.py stop <call_id>
"""
import os
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# one id names this stream, and stop names it again
CONTROL_ID = "support-audio"

# the token your endpoint checks on the upgrade request
STREAM_TOKEN = os.getenv("STREAM_BEARER_TOKEN", "")

# the spec's three tracks
TRACKS = ("inbound_track", "outbound_track", "both_tracks")


def start(call_id, url, track="both_tracks", control_id=CONTROL_ID,
          status_url=None, tag=None):
    """Open the stream. Returns whatever the platform says about the command."""
    if not url.startswith("wss://"):
        # the spec: TLS is required, and plain ws:// is rejected
        raise ValueError(f"stream url must start with wss://, not {url!r}")
    if track not in TRACKS:
        raise ValueError(f"track must be one of {TRACKS}, not {track!r}")
    params = {"control_id": control_id, "url": url, "track": track,
              "codec": "PCMU", "name": "support"}
    if STREAM_TOKEN:
        # arrives at your endpoint as Authorization: Bearer <token>
        params["authorization_bearer_token"] = STREAM_TOKEN
    if tag:
        # your own metadata, handed to the endpoint when it connects
        params["custom_parameters"] = {"tag": tag}
    if status_url:
        params["status_url"] = status_url
        params["status_url_method"] = "POST"
    return client.calling.stream(call_id, **params)


def stop(call_id, control_id=CONTROL_ID):
    """End the stream. The call carries on."""
    return client.calling.stream_stop(call_id, control_id=control_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    if not call_id:
        print(__doc__)
    elif cmd == "start":
        print(start(call_id, *rest))
    elif cmd == "stop":
        print(stop(call_id))
    else:
        print(__doc__)
