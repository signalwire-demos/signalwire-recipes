"""Start, steer and stop live translation on a call in progress.

`calling.live_translate` carries one `action`, and the spec documents four:
`start`, `inject`, `summarize` and `stop`. Together they turn translation into
something your backend switches on partway through a call, speaks into, and
asks for a summary of, rather than something the document decided up front.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py start <call_id> en-US es-ES
    python app.py say <call_id> "A supervisor is joining."
    python app.py summary <call_id> https://your-host/summary
    python app.py stop <call_id>
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# the spec's two directions, which are also the two sides of the call
DIRECTIONS = ("remote-caller", "local-caller")


def start(call_id, from_lang="en-US", to_lang="es-ES", webhook=None):
    """Translate both sides, each hearing the other's language."""
    action = {"start": {"from_lang": from_lang, "to_lang": to_lang,
                        "direction": list(DIRECTIONS),
                        "speech_engine": "deepgram", "live_events": True}}
    if webhook:
        # translation events land here while the call runs
        action["start"]["webhook"] = webhook
    return client.calling.live_translate(call_id, action=action)


def say(call_id, message, direction="remote-caller"):
    """Speak a line into the conversation, translated on the way."""
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}, not {direction!r}")
    action = {"inject": {"message": message, "direction": direction}}
    return client.calling.live_translate(call_id, action=action)


def summary(call_id, webhook, prompt=None):
    """Ask for a summary of the translated conversation so far."""
    inner = {"webhook": webhook}
    if prompt:
        inner["prompt"] = prompt
    return client.calling.live_translate(call_id, action={"summarize": inner})


def stop(call_id):
    """End translation. The call carries on untranslated."""
    return client.calling.live_translate(call_id, action={"stop": {}})


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    actions = {"start": start, "say": say, "summary": summary, "stop": stop}
    if not call_id or cmd not in actions:
        print(__doc__)
    else:
        print(actions[cmd](call_id, *rest))
