"""Reduce background noise on a call.

Two ways to switch noise reduction on and off for one leg. In SWML, `denoise`
starts it and
`stop_denoise` stops it; both take no parameters. Over REST, the same pair are
the call commands `calling.denoise` and `calling.denoise.stop`, addressed to a
live call by id, so your backend can toggle it mid-call.

Written against signalwire-sdk 3.0.1 (SWMLService, RestClient.calling).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def build(service=None):
    """The document: noise reduction on while the caller records, off after."""
    service = service or SWMLService(name="denoise", route="/denoise")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("denoise", {})
    service.add_verb("play", {"url": "say:Leave your message after the tone."})
    service.add_verb("record", {"beep": True, "max_length": 60, "terminators": "#"})
    service.add_verb("stop_denoise", {})
    service.add_verb("play", {"url": "say:Thanks. Goodbye."})
    service.add_verb("hangup", {})
    return service


def quiet(call_id):
    """Switch noise reduction on for a live call, from your backend."""
    return client.calling.denoise(call_id)


def loud(call_id):
    """Switch it off again."""
    return client.calling.denoise_stop(call_id)


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
