"""Inject a message into a live AI call.

One REST command, `calling.ai_message`, addresses a call that is already
running an AI agent, by id. The vendored REST spec describes `role: system` as
injecting "instructions or context that modify the AI's behavior
mid-conversation without the caller hearing it". The same command carries
`global_data` to merge into the session, or `reset` with a new system prompt.

Your backend needs the call id. The tool webhook body carries it as `call_id`
(docs: ai-swaig-tool-webhook).

Written against signalwire-sdk 3.0.1 (RestClient.calling).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def nudge(call_id, instruction):
    """A system-role message, per the spec one the caller does not hear."""
    return client.calling.ai_message(call_id, role="system",
                                     message_text=instruction)


def share(call_id, data):
    """Merge keys into the session's global_data mid-call."""
    return client.calling.ai_message(call_id, global_data=data)


def restart(call_id, system_prompt):
    """A reset: full_reset with a new system_prompt, as the spec defines it."""
    return client.calling.ai_message(
        call_id, reset={"full_reset": True, "system_prompt": system_prompt})


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise SystemExit("usage: python app.py <call_id> <instruction>")
    print(nudge(sys.argv[1], " ".join(sys.argv[2:])))
