"""Add a phone caller to a video room.

Two pieces. Over REST, `POST /api/fabric/resources/conference_rooms` creates
the room; the spec requires `name` and `enable_room_previews`. In SWML, the
`join_room` verb takes that `name`, and the bundled schema describes it as
joining the named room. Point a number's webhook at the document and the phone
leg is what joins.

Written against signalwire-sdk 3.0.1 (SWMLService, RestClient.fabric).
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

ROOM = os.getenv("ROOM_NAME", "workshop-standup")


def create_room(name=ROOM):
    """The room resource. `name` is what join_room refers to."""
    return client.fabric.conference_rooms.create(
        name=name, display_name="Workshop stand-up", enable_room_previews=False,
        max_members=10)


def build(service=None):
    """The document a phone number runs to join the room."""
    service = service or SWMLService(name="join", route="/join")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("play", {"url": "say:Joining the workshop stand-up. One moment."})
    service.add_verb("join_room", {"name": ROOM})
    service.add_verb("hangup", {})
    return service


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "create-room":
        print(create_room())
    else:
        build().serve(port=int(os.getenv("PORT", "8080")))
