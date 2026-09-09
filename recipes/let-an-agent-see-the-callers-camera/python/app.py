"""Let an agent see the caller's camera.

Two `ai.params` and one filler. The bundled schema documents `enable_vision`
as "Enables visual input processing for the AI Agent. When set to `true`, the
AI Agent will be able to utilize visual processing capabilities, while
leveraging the `get_visual_input` function." `vision_model` names the model:
"Allowed values are `gpt-4o-mini`, `gpt-4.1-mini`, and `gpt-4.1-nano`." The
`get_visual_input` function is the platform's; you do not define it. What you
can give it is an internal filler, a phrase filed under its name.

Written against signalwire-sdk 3.0.1 (AgentBase.set_params,
set_internal_fillers).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
LOOKING = ["Let me take a look.", "One moment while I look at that."]


class EyesAgent(AgentBase):
    def __init__(self):
        super().__init__(name="eyes", route="/eyes")
        self.prompt_add_section(
            "Role",
            "You are the workshop desk at Ridgeline Cycles, on a video call. When the "
            "caller shows you a part or a problem, look at it before you answer, and "
            "describe what you see before you give advice.")
        # the switch and the model; the platform supplies get_visual_input
        self.set_params({"enable_vision": True, "vision_model": VISION_MODEL})
        # the phrases filed under the platform's function name
        self.set_internal_fillers({"get_visual_input": {"en-US": LOOKING}})


agent = EyesAgent()

if __name__ == "__main__":
    agent.run()
