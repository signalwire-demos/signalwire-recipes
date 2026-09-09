"""Forward calls to a phone and keep the caller's number.

A forwarded call usually shows the forwarding number on the phone that rings,
so whoever answers cannot see who is really calling. `connect` takes a `from`,
which the bundled schema describes as "the caller ID to use when dialing the
number". Set it to the inbound `call.from` and the forwarded phone shows the
original caller.

SignalWire fetches this document with the inbound call webhook, whose body
carries `call.from`, so the handler reads the caller and writes it back into
the `connect`. Nothing is templated; the number the platform sent is the
number the platform gets.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.

    python app.py            # serves POST /swml
"""
import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

# the phone that should ring; swap for your on-call rota
FORWARD_TO = os.getenv("FORWARD_TO", "+15550100001")
RING_FOR = int(os.getenv("RING_FOR", "25"))

# The webhook serves a routing document to whoever asks; SignalWire fetches it
# with the credentials in the URL you give it, so the route wants them too.
AUTH_USER = os.getenv("SWML_BASIC_AUTH_USER")
AUTH_PASSWORD = os.getenv("SWML_BASIC_AUTH_PASSWORD")
if not (AUTH_USER and AUTH_PASSWORD):
    raise SystemExit("SWML_BASIC_AUTH_USER and SWML_BASIC_AUTH_PASSWORD are required; "
                     "see .env.example")


def document(caller):
    """Connect to the forwarding target, presenting the caller's own number."""
    service = SWMLService(name="forward", route="/swml")
    connect = {"to": FORWARD_TO, "timeout": RING_FOR}
    if caller:
        # the caller ID the ringing phone displays. Without a caller id the
        # platform picks, so the key is left out rather than set to nothing
        connect["from"] = caller
    service.add_verb("connect", connect)
    # 3.0.1 renders the document as a JSON string
    return json.loads(service.render_document())


app = Flask(__name__)


@app.post("/swml")
def swml():
    auth = request.authorization
    if not (auth and auth.username == AUTH_USER and auth.password == AUTH_PASSWORD):
        return Response(status=401, headers={"WWW-Authenticate": 'Basic realm="swml"'})
    payload = request.get_json(force=True)
    return jsonify(document((payload.get("call") or {}).get("from")))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
