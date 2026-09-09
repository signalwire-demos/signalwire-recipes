"""Play a prompt and collect digits or speech over REST.

`calling.play` speaks text or plays a file into a live call, `calling.play.stop`
cuts it short, and `calling.collect` gathers keypad digits or speech. Each is
one POST to /api/calling/calls addressed to the call id. Results do not come
back in the HTTP response: the platform posts them to the `status_url` you
give, so a collect without one is refused here before it is sent.

Written against signalwire-sdk 3.0.1 (RestClient.calling).

    python app.py say <call_id> "Please key in your account number"
    python app.py stop <call_id>
    python app.py volume <call_id> -6
    python app.py digits <call_id> https://your-host/collect-events
    python app.py speech <call_id> https://your-host/collect-events
"""
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()

# one id per operation type; stop and collect.stop name them
PLAY_ID = "agent-desk-prompt"
COLLECT_ID = "agent-desk-input"


def say(call_id, text, control_id=PLAY_ID, status_url=None):
    """Speak `text` to the caller. Playback events go to status_url if given."""
    item = {"type": "tts", "params": {"text": text}}
    params = {"control_id": control_id, "play": [item]}
    if status_url:
        params["status_url"] = status_url
    return client.calling.play(call_id, **params)


def play_file(call_id, url, control_id=PLAY_ID):
    """Play an audio file from an HTTP(S) URL instead of speaking text."""
    item = {"type": "audio", "params": {"url": url}}
    return client.calling.play(call_id, control_id=control_id, play=[item])


def set_volume(call_id, volume, control_id=PLAY_ID):
    """Adjust a playing prompt, in dB. The spec's range is -40 to 40."""
    try:
        # the command line hands this over as a string
        volume = float(volume)
    except (TypeError, ValueError):
        raise ValueError(f"volume must be a number of dB, not {volume!r}") from None
    if not -40 <= volume <= 40:
        raise ValueError(f"volume must be between -40 and 40 dB, not {volume!r}")
    return client.calling.play_volume(call_id, control_id=control_id, volume=volume)


def stop_playback(call_id, control_id=PLAY_ID):
    """Cut the prompt short, for example when the caller starts keying digits."""
    return client.calling.play_stop(call_id, control_id=control_id)


def _needs_status_url(status_url):
    # the result arrives only by webhook; without one the collect is unobservable
    if not status_url:
        raise ValueError("a collect needs a status_url to deliver its result")


def ask_digits(call_id, status_url, max_digits=10, control_id=COLLECT_ID):
    """Collect up to max_digits keypad digits, ended early by #."""
    _needs_status_url(status_url)
    digits = {"max": max_digits, "terminators": "#", "digit_timeout": 5}
    # start_input_timers defaults to false, and then initial_timeout never runs
    return client.calling.collect(call_id, control_id=control_id, digits=digits,
                                  initial_timeout=10, start_input_timers=True,
                                  status_url=status_url)


def ask_speech(call_id, status_url, language="en-US", control_id=COLLECT_ID):
    """Collect one spoken answer, ended by 1.5 seconds of silence."""
    _needs_status_url(status_url)
    speech = {"end_silence_timeout": 1.5, "speech_timeout": 15, "language": language}
    return client.calling.collect(call_id, control_id=control_id, speech=speech,
                                  initial_timeout=10, start_input_timers=True,
                                  status_url=status_url)


def stop_collect(call_id, control_id=COLLECT_ID):
    """Give up waiting for input."""
    return client.calling.collect_stop(call_id, control_id=control_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    call_id = args[1] if len(args) > 1 else ""
    rest = args[2:]
    actions = {"say": say, "file": play_file, "stop": stop_playback,
               "volume": set_volume, "digits": ask_digits,
               "speech": ask_speech, "cancel": stop_collect}
    if cmd in actions and call_id:
        print(actions[cmd](call_id, *rest))
    else:
        print(__doc__)
