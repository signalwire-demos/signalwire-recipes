"""Remember a returning caller across calls.

Two `ai.params` do the work. `save_conversation` makes the platform post a
summary of the conversation when the call ends, and `conversation_id` names
the conversation it belongs to. Name it after the caller's number and the next
call from that number can ask for the summary back: the platform POSTs
`action: fetch_conversation` to the same `post_prompt_url`, and whatever
`on_summary` returns is the answer. The SDK's post-prompt route says it expects
`conversation_summary` in that response (core/mixins/web_mixin.py).

The summaries live in a file here, keyed by conversation id, because the call
that saves and the call that asks are different requests to your server.

Written against signalwire-sdk 3.0.1 (AgentBase, set_dynamic_config_callback).

    python app.py          # serves /front-desk/ and /front-desk/post_prompt
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

# where each caller's last summary lives; swap for your database
MEMORY_PATH = Path(os.getenv("MEMORY_PATH", "caller-memory.json"))


def conversation_id(number):
    """One conversation per caller, keyed on the digits of the number.

    A caller with no digits (anonymous, or a SIP URI with none) gets None, so
    no memory is kept rather than one memory shared by every such caller.
    """
    digits = re.sub(r"\D", "", number or "")
    return "caller-" + digits if digits else None


def _load():
    if not MEMORY_PATH.exists():
        return {}
    return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))


def _save(memory):
    tmp = MEMORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    os.replace(tmp, MEMORY_PATH)


def configure(query_params, body_params, headers, agent):
    """Runs on every request, against an ephemeral copy of the agent.

    The SWML request body carries the call, and `call.from` is the caller.
    """
    cid = conversation_id((body_params.get("call") or {}).get("from"))
    if cid:
        agent.set_params({"save_conversation": True, "conversation_id": cid})


class FrontDesk(AgentBase):
    def __init__(self):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", "You answer the phone for Ridgeline Cycles, "
                                        "a bike shop. Be brief and warm.")
        self.prompt_add_section("Memory", "If a summary of a previous call is "
                                          "available, greet the caller as someone "
                                          "you have spoken to and pick up from it.")
        # a post_prompt is what makes the SDK emit post_prompt_url, which
        # save_conversation needs; the summary it asks for is what gets kept
        self.set_post_prompt("Summarise the call in two sentences, including "
                             "anything the caller asked you to remember.")
        self.set_dynamic_config_callback(configure)

    def on_summary(self, summary, raw_data=None):
        """Save at the end of a call; answer a fetch at the start of the next."""
        raw_data = raw_data or {}
        cid = raw_data.get("conversation_id")
        if raw_data.get("action") == "fetch_conversation":
            remembered = _load().get(cid)
            # the platform reads conversation_summary from this response
            return {"conversation_summary": remembered} if remembered else {}
        if summary and cid:
            memory = _load()
            memory[cid] = summary if isinstance(summary, str) else json.dumps(summary)
            _save(memory)
        return None


agent = FrontDesk()

if __name__ == "__main__":
    agent.serve(port=int(os.getenv("PORT", "3000")))
