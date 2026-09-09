"""Call from a browser - the server half.

A browser cannot hold your project API token, so a small server mints a
Subscriber Access Token for the signed-in user and hands it to the page. The
page (typescript/) uses the token to connect and dial a phone number or a
Resource address over WebRTC.

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

DEFAULT_DESTINATION = os.getenv("DIAL_DESTINATION", "/public/support")


def token_for(user_reference, display_name=None):
    """A Subscriber Access Token identifies one signed-in user; it can dial
    anywhere the user may reach and can receive inbound calls too."""
    body = {"reference": user_reference}
    if display_name:
        body["display_name"] = display_name
    return client.fabric.tokens.create_subscriber_token(**body)


@app.post("/token")
def token():
    # In a real app, `reference` is the authenticated user's id from your session.
    body = request.json or {}
    t = token_for(body.get("user", "demo-user"), body.get("display_name"))
    return jsonify(token=t["token"], destination=body.get("to", DEFAULT_DESTINATION))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
