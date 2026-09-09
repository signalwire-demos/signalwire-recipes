"""Control when a caller can interrupt a voice agent.

Interruption and turn-taking are `ai.params`, not prompt sentences.
`enable_barge` says which speech events may cut the agent off, `barge_min_words`
how many words it takes, `static_greeting_no_barge` protects the greeting, and
`end_of_speech_timeout`, `first_word_timeout` and `speech_event_timeout` decide
when the caller has finished. The schema bounds each one, and the verifier
proves the rendered document carries exactly these keys within those bounds.

Written against signalwire-sdk 3.0.1.

    python app.py            # serves /front-desk/
"""
import json
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()


def barge_value(raw):
    """`enable_barge` is a string or a boolean, and false is how you turn it off.

    An environment variable is always a string, so "false" has to become the
    boolean or the document carries a value the reference does not list.
    """
    if raw.strip().lower() == "false":
        return False
    if raw.strip().lower() == "true":
        return True
    return raw


def int_value(raw, fallback):
    """An integer setting. A typo in .env should stop the process, not ship."""
    if raw is None or not raw.strip():
        return fallback
    return int(raw)                      # ValueError names the bad value


def number_value(raw, fallback):
    """A number setting. Whole values stay integers so both surfaces agree."""
    if raw is None or not raw.strip():
        return fallback
    value = float(raw)
    return int(value) if value.is_integer() else value


def env_int(name, default):
    return int_value(os.getenv(name), default)


def env_bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


# The line the platform speaks before the model does. It has to be a
# static_greeting, because static_greeting_no_barge is what protects it; a
# prompt telling the model to open with a line protects nothing.
GREETING = "Ridgeline Cycles, how can I help?"

# The turn-taking settings. Each is documented on ai.params; the schema holds
# the bounds the verifier checks, and the defaults where it states one.
TURN_TAKING = {
    # what static_greeting_no_barge below refers to
    "static_greeting": GREETING,
    # which events interrupt the agent: "complete", "partial", "all", or a
    # boolean. The default is "complete,partial"; false turns barging off
    "enable_barge": barge_value(os.getenv("ENABLE_BARGE", "complete,partial")),
    # how many words the caller must say before it counts as an interruption, 1-99
    "barge_min_words": env_int("BARGE_MIN_WORDS", 3),
    # while the caller talks over the agent, the agent does not answer them (default)
    "transparent_barge": env_bool("TRANSPARENT_BARGE", True),
    # a cough is not an interruption
    "interrupt_on_noise": env_bool("INTERRUPT_ON_NOISE", False),
    # the opening line plays through even if the caller starts talking
    "static_greeting_no_barge": env_bool("STATIC_GREETING_NO_BARGE", True),
    # ms of silence that ends the caller's turn, 250-10000, default 700
    "end_of_speech_timeout": env_int("END_OF_SPEECH_TIMEOUT", 700),
    # ms to wait for a first word once speech is detected, 0-10000, default 1000
    "first_word_timeout": env_int("FIRST_WORD_TIMEOUT", 1000),
    # ms to wait for a speech event, 0-10000, default 1400
    "speech_event_timeout": env_int("SPEECH_EVENT_TIMEOUT", 1400),
    # how loud the caller must be to be heard, 0.0-100.0 dB, default 52
    "energy_level": number_value(os.getenv("ENERGY_LEVEL"), 52),
    # end the turn on sentence-ending punctuation in the partial transcript (default)
    "enable_turn_detection": env_bool("ENABLE_TURN_DETECTION", True),
}


class FrontDesk(AgentBase):
    def __init__(self, turn_taking=None):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", "You answer the phone for Ridgeline Cycles, "
                                        "a bike shop. Be brief and warm.")
        # the whole recipe: turn-taking is configuration, not prose
        self.set_params(TURN_TAKING if turn_taking is None else turn_taking)


def render(turn_taking=None):
    """The document the platform receives, as a dict."""
    return json.loads(FrontDesk(turn_taking)._render_swml())


agent = FrontDesk()

if __name__ == "__main__":
    for name in ("SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"):
        if not os.getenv(name):
            raise SystemExit(f"{name} is required; see .env.example")
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
