"""Mint a guest token that can only dial what you list.

A Subscriber token belongs to a person and can reach whatever that person can.
A guest token belongs to nobody, and `allowed_addresses` is the whole of its
authority: a visitor holding one can dial the addresses on the list and nothing
else.

The list is built server-side from the page the visitor is on. It is never
taken from the request, because a value the browser supplies is a value the
browser can change.

Written against signalwire-sdk 3.0.1 (RestClient.fabric) and Flask.
"""
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

# What each page on the site is allowed to reach. The addresses live here,
# not in the browser.
DESKS = {
    "support": ["/public/support"],
    "sales": ["/public/sales"],
    # a page may offer a choice, within a list you decided
    "contact": ["/public/support", "/public/sales"],
}

# The documented ceiling for a guest token.
MAX_ADDRESSES = 10

# Short, because a page reload can mint another.
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "900"))

app = Flask(__name__)


def guest_token_for(page):
    """A token whose reach is exactly the desks that page is allowed."""
    allowed = DESKS.get(page)
    if not allowed:
        raise KeyError(page)
    if len(allowed) > MAX_ADDRESSES:
        raise ValueError(f"{page}: {len(allowed)} addresses exceeds the "
                         f"documented maximum of {MAX_ADDRESSES}")
    return client.fabric.tokens.create_guest_token(
        allowed_addresses=allowed,
        expire_at=int(time.time()) + TOKEN_TTL_SECONDS,
    )


@app.post("/token")
def token():
    """The browser selects a key. It never supplies an address.

    A visitor can ask for any known page, so every desk in DESKS is reachable
    by anyone. What they cannot do is add an address that is not in the table.
    """
    page = (request.get_json(silent=True) or {}).get("page", "")
    try:
        minted = guest_token_for(page)
    except KeyError:
        return jsonify({"error": "unknown page"}), 404
    # only the token goes back: the project credentials stay here
    return jsonify({"token": minted.get("token")})


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
