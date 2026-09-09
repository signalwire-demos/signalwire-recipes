"""Reject callers on a blocklist before answering.

SignalWire fetches your document with the inbound call webhook, whose body
carries `call.from`. Your handler reads it and decides. A number on the list
gets a one-verb document, `hangup` with a reason, and no `answer` before it, so
the call is refused rather than picked up. Everyone else gets `answer` and
`connect`. The list is yours; the platform never sees it.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.

    python app.py            # serves POST /swml
"""
import json
import os
import re

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

# where allowed callers end up; swap for your queue or agent
DESTINATION = os.getenv("DESTINATION", "+15550100001")

# the numbers to refuse, in any format; compared by digits. Swap for your table
BLOCKLIST = {"+15555550100", "+1 (555) 555-0101"}

# the schema's reasons are hangup, busy and decline; decline tells the far end
# the call was refused, busy makes it look like a busy line
REASON = os.getenv("REJECT_REASON", "decline")

# The webhook serves a routing document to whoever asks; SignalWire fetches it
# with the credentials in the URL you give it, so the route wants them too.
AUTH_USER = os.getenv("SWML_BASIC_AUTH_USER")
AUTH_PASSWORD = os.getenv("SWML_BASIC_AUTH_PASSWORD")
if not (AUTH_USER and AUTH_PASSWORD):
    raise SystemExit("SWML_BASIC_AUTH_USER and SWML_BASIC_AUTH_PASSWORD are required; "
                     "see .env.example")


def digits(number):
    """+1 (555) 555-0101 and 15555550101 are the same caller."""
    return re.sub(r"\D", "", number or "")


BLOCKED = {digits(n) for n in BLOCKLIST}


def is_blocked(caller):
    """True for a listed number. An absent caller id is not on any list."""
    d = digits(caller)
    return bool(d) and d in BLOCKED


def document(caller):
    """The SWML for this caller: refused before answering, or answered and connected."""
    service = SWMLService(name="screen", route="/swml")
    if is_blocked(caller):
        # no answer verb: the call is declined, not picked up and dropped
        service.add_verb("hangup", {"reason": REASON})
    else:
        service.add_verb("answer", {})
        service.add_verb("connect", {"to": DESTINATION})
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
