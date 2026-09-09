"""Create a video room and join from the browser.

Server side: create a Conference Room resource over REST (it gets a Fabric
address, /public/<name>), then mint a Guest token per participant that can dial
only that address. Browser side (typescript/): the participant dials the room
with audio and video.

Written against signalwire-sdk 3.0.1 (RestClient.fabric) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)
client = RestClient()

ROOM = os.getenv("ROOM_NAME", "team-standup")
TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "60"))


def create_room(name=ROOM):
    """A Conference Room is a Fabric resource; its address is /public/<name>."""
    return client.fabric.conference_rooms.create(
        name=name,
        display_name=name.replace("-", " ").title(),
        max_members=25,
        layout="grid-responsive",
        quality="720p",
        record_on_start=False,
        enable_room_previews=True,   # documented as required by the create endpoint
    )


def guest_token_for(room=ROOM, expire_at=None):
    """Outbound-only token pinned to the room's address (max 10 addresses)."""
    body = {"allowed_addresses": [f"/public/{room}"]}
    if expire_at:
        body["expire_at"] = expire_at
    return client.fabric.tokens.create_guest_token(**body)


@app.post("/rooms")
def rooms():
    return jsonify(create_room((request.json or {}).get("name", ROOM)))


@app.post("/token")
def token():
    """The browser asks for a token; it never sees the project API token."""
    room = (request.json or {}).get("room", ROOM)
    t = guest_token_for(room)
    return jsonify(token=t["token"], destination=f"/public/{room}")


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
