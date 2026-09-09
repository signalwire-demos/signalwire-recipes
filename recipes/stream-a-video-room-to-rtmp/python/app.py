"""Stream a video room to RTMP.

One POST asks the platform to stream a room's session to an RTMP or RTMPS
server of yours.
The vendored REST spec (tools/openapi/rest.json) documents
`POST /api/video/rooms/{id}/streams` with one required field, `url`, described
as "RTMP or RTMPS URL. This must be the address of a server accepting incoming
RTMP/RTMPS streams." The response carries the stream's `id`. The spec titles
`PUT /api/video/streams/{id}` "Update stream", with the same required `url`,
and `DELETE /api/video/streams/{id}` "Delete stream", answering 204.

Written against signalwire-sdk 3.0.1 (RestClient.video).
"""
import os

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

# the URL may contain a stream key, so it lives in .env and not here
RTMP_URL = os.getenv("RTMP_URL")


def start_stream(room_id, url=None):
    """Ask for a stream of the room to `url`. The response id is the handle."""
    url = url or RTMP_URL
    if not url:
        raise SystemExit("RTMP_URL is required to start a stream; see .env.example")
    return client.video.rooms.create_stream(room_id, url=url)


def move_stream(stream_id, url):
    """Update the stream's destination URL."""
    return client.video.streams.update(stream_id, url=url)


def stop_stream(stream_id):
    return client.video.streams.delete(stream_id)


def streams(room_id):
    """The room's streams, as the platform lists them."""
    return client.video.rooms.list_streams(room_id)


if __name__ == "__main__":
    import sys

    usage = ("usage: python app.py start <room_id> | move <stream_id> <url> | "
             "stop <stream_id> | list <room_id>")
    verb, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if verb == "start" and len(args) == 1:
        print(start_stream(args[0]))
    elif verb == "move" and len(args) == 2:
        print(move_stream(args[0], args[1]))
    elif verb == "stop" and len(args) == 1:
        print(stop_stream(args[0]))
    elif verb == "list" and len(args) == 1:
        print(streams(args[0]))
    else:
        raise SystemExit(usage)
