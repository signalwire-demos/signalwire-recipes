"""Run the same voice AI agent over text chat.

The agent below is the one a phone number reaches. The AI Chat API reaches it
too: `POST /api/ai/chat` takes a JSON-RPC 2.0 body whose `params.config_url`
is the URL this agent serves its SWML from, and SignalWire fetches the
definition server-to-server. One request is one turn. Six methods travel over
the one endpoint: `create_conversation`, `chat`, `end_conversation`, `delete`,
`chat_log` and `summarize` (the vendored REST spec, `tools/openapi/rest.json`).

`RestClient` in signalwire-sdk 3.0.1 wraps no method for this path, so the
requests go through its HTTP layer directly. Later SDK releases ship
`signalwire.ai_chat.AIChatClient` for the same wire.

Written against signalwire-sdk 3.0.1 (AgentBase, RestClient).

    python app.py serve     # the agent, at /front-desk/ behind basic auth
    python app.py chat      # a text conversation with it, from your terminal
"""
import os
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit, quote

from dotenv import load_dotenv
from signalwire import AgentBase
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

CHAT = "/api/ai/chat"
ROUTE = "/front-desk"
ROLES = ("user", "system")   # the spec's enum for params.role on `chat`


class FrontDesk(AgentBase):
    """The agent a phone call reaches. Nothing here is chat-specific."""

    def __init__(self):
        super().__init__(name="front-desk", route=ROUTE)
        self.prompt_add_section("Role", "You answer for Ridgeline Cycles, a bike shop. "
                                        "Be brief and warm.")
        self.prompt_add_section("Hours", "Open Monday to Friday, nine to five, "
                                         "Eastern time. Closed weekends.")
        self.prompt_add_section("Limits", "You cannot book repairs. Offer the shop "
                                          "number for that.")
        self.set_post_prompt("Summarise the conversation in one sentence.")


def config_url(agent, public_base=None):
    """Where the platform fetches the agent's SWML: this agent's route, with a
    trailing slash, on your public host, carrying the basic-auth pair. The
    platform gets only the URL, so the credentials travel inside it."""
    base = public_base or os.environ["AGENT_PUBLIC_URL"]
    user, password = agent.get_basic_auth_credentials()
    parts = urlsplit(base)
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{parts.netloc}"
    path = parts.path.rstrip("/") + agent.route + "/"
    return urlunsplit((parts.scheme, netloc, path, "", ""))


class ChatError(Exception):
    """A JSON-RPC error. It arrives inside an HTTP 200, so the HTTP layer
    never raises for it; `code` is the service's number (-32001 is an unknown
    conversation, -32002 an unreachable config_url)."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


class TextChannel:
    """The six methods, each one POST with a JSON-RPC 2.0 envelope."""

    def __init__(self, http=None):
        self.http = http or client._http

    def rpc(self, method, params):
        body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method,
                "params": params}
        envelope = self.http.post(CHAT, body=body)
        if "error" in envelope:
            err = envelope["error"] or {}
            raise ChatError(err.get("code"), err.get("message", ""))
        return envelope.get("result", {})

    def create(self, cid, url, user_message=None, timeout=None):
        """A conversation you name. The result carries the agent's opening
        line in `initial_message` when the agent greets first."""
        params = {"id": cid, "config_url": url}
        if user_message:
            params["user_message"] = user_message
        if timeout:
            params["conversation_timeout"] = timeout
        return self.rpc("create_conversation", params)

    def say(self, cid, message, role="user"):
        """One turn. A `system` message steers the agent without appearing as
        something the user said; anything else is refused before it is sent."""
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, not {role!r}")
        params = {"id": cid, "message": message}
        if role != "user":
            params["role"] = role
        return self.rpc("chat", params)

    def log(self, cid):
        return self.rpc("chat_log", {"id": cid}).get("chat_log", [])

    def summarize(self, cid, prompt=None):
        """A summary on demand. A failure rides the success envelope as
        `error`, so it is checked here rather than by `rpc`."""
        params = {"id": cid}
        if prompt:
            params["summary_prompt"] = prompt
        result = self.rpc("summarize", params)
        if "summary" not in result:
            raise ChatError(None, result.get("error", "no summary produced"))
        return result["summary"]

    def end(self, cid):
        """Ends the conversation and runs post-processing (the post_prompt)."""
        return self.rpc("end_conversation", {"id": cid})

    def delete(self, cid):
        """Removes the conversation with no post-processing."""
        return self.rpc("delete", {"id": cid})


def converse(channel, url, lines=input, out=print):
    """A terminal conversation: create, turns until 'bye', then end."""
    cid = "text-" + uuid.uuid4().hex
    made = channel.create(cid, url)
    if made.get("initial_message"):
        out("agent:", made["initial_message"])
    while True:
        text = lines("you: ").strip()
        if not text or text.lower() == "bye":
            break
        out("agent:", channel.say(cid, text)["response"])
    out("summary:", channel.summarize(cid))
    channel.end(cid)


agent = FrontDesk()

if __name__ == "__main__":
    if sys.argv[1:] == ["serve"]:
        agent.serve(port=int(os.getenv("PORT", "3000")))
    elif sys.argv[1:] == ["chat"]:
        converse(TextChannel(), config_url(agent))
    else:
        print(__doc__)
