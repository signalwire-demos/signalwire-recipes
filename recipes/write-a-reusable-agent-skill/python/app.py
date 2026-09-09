"""Use the reusable skill from an agent.

`register_skill` puts a class you wrote into the registry under its own
`SKILL_NAME`. After that `add_skill("store_hours")` is all the agent needs, and
the skill brings its tools, hints and prompt sections with it.

Two instances of the same skill run side by side here, one per branch, each
configured by `params`. That is what `SUPPORTS_MULTIPLE_INSTANCES` buys.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase
from signalwire.skills import skill_registry

from skill import StoreHoursSkill

# the SDK does not read .env for you
load_dotenv()

# a class in your own code becomes addressable by name
skill_registry.register_skill(StoreHoursSkill)

WEEKEND_CLOSED = {
    "monday": "8am to 5pm", "tuesday": "8am to 5pm",
    "wednesday": "8am to 5pm", "thursday": "8am to 5pm",
    "friday": "8am to 5pm", "saturday": "closed", "sunday": "closed",
}


class ShopAgent(AgentBase):
    def __init__(self):
        super().__init__(name="shop", route="/shop")
        self.prompt_add_section(
            "Role",
            "You answer the phone for Ridgeline Cycles, which has a shop and "
            "a workshop.",
        )
        # the shop, on default hours
        self.add_skill("store_hours", {
            "tool_name": "shop_hours",
            "location": "the shop",
        })
        # the workshop: same class, different configuration, distinct
        # tool_name so it is a second instance rather than a duplicate
        self.add_skill("store_hours", {
            "tool_name": "workshop_hours",
            "location": "the workshop",
            "hours": WEEKEND_CLOSED,
        })


agent = ShopAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
