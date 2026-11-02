"""Add a group chat to a video room: the server half.

The chat is the room's own conversation, reached through the room's Fabric
address, so the browser needs a token that says who is typing. A Subscriber
Access Token does that: one per user, minted here with the project API token
the page never sees. The browser (typescript/) dials the room with audio and
video and then reads and writes the room's text thread through the same call.

Written against signalwire-sdk 3.0.1 (RestClient.fabric.tokens) and Flask.
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


def token_for(user_reference, display_name=None):
    """One Subscriber Access Token per signed-in user.

    `reference` is the string SignalWire uses to identify the user. Each message
    in the thread carries the sender's address, so two people need two tokens,
    and the guide notes that one token in two tabs logs stale-event errors.
    `display_name` is what the other participants see.
    """
    body = {"reference": user_reference}
    if display_name:
        body["display_name"] = display_name
    return client.fabric.tokens.create_subscriber_token(**body)


@app.post("/token")
def token():
    """The browser asks for its token; the project API token stays here."""
    # In a real app, `user` is the authenticated user's id from your session.
    body = request.json or {}
    user = body.get("user")
    if not user:
        return jsonify(error="user is required"), 400
    t = token_for(user, body.get("display_name"))
    room = body.get("room", ROOM)
    return jsonify(token=t["token"], destination=f"/public/{room}")


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
