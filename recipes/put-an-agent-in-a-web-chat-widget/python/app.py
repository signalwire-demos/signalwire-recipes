"""Put an AI agent in a web chat widget.

A page cannot hold a SignalWire API token: the token carries the whole
project. This gateway holds it, and the page learns two things, the gateway's
URL and a publishable key. The gateway injects `config_url` itself, so a
visitor cannot pick which agent runs; it signs a handle per conversation, so
an id cannot be forged or guessed; and it caps new conversations per window
and turns per conversation, which bounds what a leaked key can cost.

The wire is modelled on the SDK's own `ChatGateway` (newer than the pinned
3.0.1): `POST /chat/` with the key in `Authorization: Bearer`, a `method` of
`start`, `chat`, `log` or `end`, and an `X-Chat-Handle` header on the
response that minted the handle. Upstream, every method is one JSON-RPC 2.0
POST to `/api/ai/chat` (the vendored REST spec, `tools/openapi/rest.json`).

Written against signalwire-sdk 3.0.1 (RestClient) and Flask.

    python app.py          # the page at /, the gateway at /chat/
"""
import hashlib
import hmac
import json
import os
import time
import uuid
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

CHAT = "/api/ai/chat"
# the agent this gateway may talk to; never accepted from the request
CONFIG_URL = os.environ["AGENT_CONFIG_URL"]
KEY = os.environ["CHAT_GATEWAY_KEY"]              # the page carries this
SECRET = os.environ["CHAT_GATEWAY_SECRET"].encode()   # the page never sees this
ALLOWED_ORIGINS = {o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
                   if o.strip()}
MAX_NEW = int(os.getenv("MAX_NEW_CONVERSATIONS", "60"))
WINDOW = int(os.getenv("WINDOW_SECONDS", "60"))
MAX_TURNS = int(os.getenv("MAX_TURNS", "200"))
TIMEOUT = int(os.getenv("CONVERSATION_TIMEOUT", "1800"))
PAGE = (Path(__file__).resolve().parent.parent / "web" / "widget.html").read_text("utf-8")
VISIBLE_ROLES = ("user", "assistant")   # a page redraws these; never the prompt or tools

# counters live in this process; behind replicas each keeps its own
_mints = deque()
_turns = {}


def rpc(method, params, http=None):
    """One JSON-RPC 2.0 request. An error arrives inside an HTTP 200."""
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": params}
    envelope = (http or client._http).post(CHAT, body=body)
    if "error" in envelope:
        err = envelope["error"] or {}
        raise RuntimeError(f"{err.get('code')}: {err.get('message', '')}")
    return envelope.get("result", {})


def sign(cid):
    return hmac.new(SECRET, cid.encode(), hashlib.sha256).hexdigest()[:32]


def mint_handle():
    """A fresh conversation id and the handle that proves this server made it."""
    cid = "chat-" + uuid.uuid4().hex
    return cid, f"{cid}.{sign(cid)}"


def read_handle(handle):
    """The conversation id inside a handle, or None when it was not ours."""
    cid, _, sig = (handle or "").rpartition(".")
    if not cid or not hmac.compare_digest(sig, sign(cid)):
        return None
    return cid


def refuse(status, reason):
    """Coarse on purpose: a finer reason lets a caller map the caps by probing."""
    abort(Response(json.dumps({"error": reason}), status=status,
                   mimetype="application/json"))


def check_key_and_origin():
    if request.headers.get("Authorization") != f"Bearer {KEY}":
        refuse(401, "key")
    origin = request.headers.get("Origin")
    local = origin and (origin.startswith("http://localhost")
                        or origin.startswith("http://127.0.0.1"))
    if origin and not local and origin not in ALLOWED_ORIGINS:
        refuse(403, "origin")


def charge_mint():
    now = time.time()
    while _mints and _mints[0] < now - WINDOW:
        _mints.popleft()
    if len(_mints) >= MAX_NEW:
        refuse(429, "limit")
    _mints.append(now)


def charge_turn(cid):
    if _turns.get(cid, 0) >= MAX_TURNS:
        refuse(429, "limit")
    _turns[cid] = _turns.get(cid, 0) + 1


app = Flask(__name__)


@app.get("/")
def index():
    return Response(PAGE.replace("__CHAT_KEY__", KEY), mimetype="text/html")


@app.post("/chat/")
def gateway():
    check_key_and_origin()
    body = request.get_json(silent=True) or {}
    method = body.get("method", "chat")
    if method == "start":
        charge_mint()
        cid, handle = mint_handle()
        made = rpc("create_conversation",
                   {"id": cid, "config_url": CONFIG_URL, "conversation_timeout": TIMEOUT})
        out = jsonify({"greeting": made.get("initial_message"),
                       "status": made.get("status"), "timeout": TIMEOUT})
        out.headers["X-Chat-Handle"] = handle
        return out
    cid = read_handle(body.get("handle"))
    if not cid:
        refuse(403, "handle")
    if method == "chat":
        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            refuse(400, "malformed")
        charge_turn(cid)
        # the visitor is always the user; a role or a config_url in the body is ignored
        return jsonify(rpc("chat", {"id": cid, "message": message}))
    if method == "log":
        entries = rpc("chat_log", {"id": cid}).get("chat_log", [])
        visible = [e for e in entries if e.get("role") in VISIBLE_ROLES]
        return jsonify({"messages": visible})
    if method == "end":
        rpc("end_conversation", {"id": cid})
        _turns.pop(cid, None)
        return jsonify({"status": "ended"})
    refuse(400, "malformed")


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
