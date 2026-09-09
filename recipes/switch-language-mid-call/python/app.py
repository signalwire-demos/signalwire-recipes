"""Switch language mid-call.

An agent that answers in whatever language the caller is speaking, and changes
partway through if they do, without a transfer and without a second agent.

Two things make it work. Each language is registered with its own TTS voice, so
the agent sounds like a speaker of that language rather than an English voice
reading Spanish. And `languages_enabled` turns the switching on: without it the
list is configuration nobody reads.

The first language registered is the one the agent opens in.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

# (name, code, voice). A voice per language: the point is that the caller
# hears a native voice, not one accent reading three languages.
LANGUAGES = [
    ("English", "en-US", "rime.spore"),
    ("Spanish", "es-ES", "rime.marisol"),
    ("French", "fr-FR", "rime.celeste"),
]


class FrontDeskAgent(AgentBase):
    def __init__(self):
        super().__init__(name="frontdesk", route="/frontdesk")
        self.prompt_add_section(
            "Role",
            "You are the front desk for a hotel in Montreal. Answer questions "
            "about check-in times, parking and breakfast.",
        )
        self.prompt_add_section(
            "Language",
            "Reply in whatever language the caller is speaking. If they change "
            "language, change with them and do not comment on it.",
        )
        for name, code, voice in LANGUAGES:
            self.add_language(name, code, voice)
        # without this the languages list is ignored
        self.set_params({"languages_enabled": True})


agent = FrontDeskAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
