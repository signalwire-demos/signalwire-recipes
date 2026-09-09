"""Give an agent a video avatar.

Three `ai.params` do it. The bundled schema documents `video_idle_file` as
"URL of a video file to play when AI is idle". It documents
`video_listening_file` as the one "to play when AI is listening to the user
speak", and `video_talking_file` as the one "to play when AI is talking". Each
carries the schema's note that it requires a call that supports video. Your
part is three URLs, one per state.

Written against signalwire-sdk 3.0.1 (AgentBase.set_params).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

BASE = os.getenv("AVATAR_BASE_URL")
if not BASE:
    raise SystemExit("AVATAR_BASE_URL is required: where idle.mp4, listening.mp4 and "
                     "talking.mp4 live")

AVATAR = {
    "video_idle_file": f"{BASE}/idle.mp4",
    "video_listening_file": f"{BASE}/listening.mp4",
    "video_talking_file": f"{BASE}/talking.mp4",
}


class FaceAgent(AgentBase):
    def __init__(self):
        super().__init__(name="face", route="/face")
        self.prompt_add_section(
            "Role",
            "You are the front desk at Ridgeline Cycles, on a video call. Greet the "
            "caller, find out what they need, and keep answers short.")
        # the three clips, one per state the schema names
        self.set_params(AVATAR)


agent = FaceAgent()

if __name__ == "__main__":
    agent.run()
