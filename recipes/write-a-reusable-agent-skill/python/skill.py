"""A reusable skill: store hours, packaged so any agent can add it.

A skill is not a helper function. It is a unit that carries everything an agent
needs to answer a class of question: the tools, the recogniser hints, and the
prompt sections that tell the model when to use them. Adding it is one line in
the agent.

`SKILL_NAME` is how the agent asks for it. `params` is how two agents get
different behaviour from the same class.

Written against signalwire-sdk 3.0.1.
"""
from signalwire.core.function_result import FunctionResult
from signalwire.skills import SkillBase

# What a shop looks like. A real skill would read a system of record.
DEFAULT_HOURS = {
    "monday": "9am to 6pm", "tuesday": "9am to 6pm",
    "wednesday": "9am to 6pm", "thursday": "9am to 8pm",
    "friday": "9am to 6pm", "saturday": "10am to 4pm",
    "sunday": "closed",
}


class StoreHoursSkill(SkillBase):
    SKILL_NAME = "store_hours"
    SKILL_DESCRIPTION = "Answer questions about when a location is open."
    SKILL_VERSION = "1.0.0"
    # two branches on one agent, each with its own params
    SUPPORTS_MULTIPLE_INSTANCES = True

    def setup(self):
        """Validate configuration before the agent is served."""
        self.location = self.params.get("location", "the shop")
        self.hours = self.params.get("hours", DEFAULT_HOURS)
        # The instance key is SKILL_NAME + "_" + tool_name, so two instances
        # need distinct tool names or the second is silently dropped. The
        # tool the model sees is named from the same value.
        self.tool_name = self.params.get("tool_name", self.SKILL_NAME)
        # a skill that cannot work should say so at startup, not mid-call
        return bool(self.hours) and all(
            day in self.hours for day in DEFAULT_HOURS
        )

    def get_hints(self):
        """Words the recogniser would otherwise guess at."""
        return [self.location, "opening hours", "closing time"]

    def _get_prompt_sections(self):
        """Told to the model, so it knows the tool exists and when to use it."""
        return [{
            "title": f"Hours for {self.location}",
            "bullets": [
                # name the tool this instance actually registers, not the
                # skill: two instances mean two different tool names
                f"Use {self.tool_name} to answer any question about when "
                f"{self.location} is open.",
                "Never guess an opening time. If the tool does not know a "
                "day, say so.",
            ],
        }]

    def register_tools(self):
        """Register with self.define_tool, so skill-level swaig_fields apply."""
        self.define_tool(
            name=self.tool_name,
            description=(
                f"Look up the opening hours of {self.location} for a given "
                f"day. Use this before stating any time."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": (
                            "The day of the week, lowercase, such as "
                            "'thursday'."
                        ),
                    }
                },
                "required": ["day"],
            },
            handler=self._lookup,
        )

    def _lookup(self, args, raw_data):
        day = (args.get("day") or "").strip().lower()
        hours = self.hours.get(day)
        if hours is None:
            return FunctionResult(
                f"UNKNOWN_DAY: {day!r} is not a day of the week. Ask the "
                f"caller which day they mean."
            )
        if hours == "closed":
            return FunctionResult(f"{self.location} is closed on {day}.")
        return FunctionResult(f"{self.location} is open {hours} on {day}.")
