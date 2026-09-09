"""Walk a caller through ordered steps.

A step is a prompt the model reads while that step is active, plus three
fields the platform reads around it:

  valid_steps    the only places the model's next_step tool can go
  functions      the only tools that exist while the step is active
  step_criteria  the sentence the runtime judges before advancing

The intake below has three steps. Every step names one tool, and every step
but the last names only the step after it, so the model is never offered a way
to skip ahead or double back. The data each step collects is written by a tool
handler, not read out of the transcript.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()


class ClaimIntakeAgent(AgentBase):
    """Three questions, in order, for a roadside assistance line."""

    def __init__(self):
        super().__init__(name="claim-intake", route="/intake")
        self.prompt_add_section(
            "Role",
            "You record a roadside assistance request. Follow the current "
            "step. Ask one thing at a time and do not move on until the "
            "tool for this step has accepted the answer.",
        )

        flow = self.define_contexts().add_context("default")

        # Each nonterminal step lists exactly one next step, so the next_step
        # tool the platform offers has one destination. Each step lists
        # exactly one function, so nothing else exists to call.
        flow.add_step("location") \
            .add_section("Current Task",
                         "Ask where the vehicle is: road or street, and the "
                         "nearest town or exit.") \
            .set_step_criteria("save_location has accepted a location.") \
            .set_functions(["save_location"]) \
            .set_valid_steps(["vehicle"])

        flow.add_step("vehicle") \
            .add_section("Current Task",
                         "Ask for the vehicle's make, model and colour.") \
            .set_step_criteria("save_vehicle has accepted a description.") \
            .set_functions(["save_vehicle"]) \
            .set_valid_steps(["problem"])

        flow.add_step("problem") \
            .add_section("Current Task",
                         "Ask what happened, then confirm the request is "
                         "recorded and end the call.") \
            .set_step_criteria("save_problem has accepted a description.") \
            .set_functions(["save_problem"]) \
            .set_end(True)

    # --- one tool per step -------------------------------------------------
    # Each handler validates, then writes to global_data. The model never
    # decides what counts as an answer; the handler does.

    @AgentBase.tool(
        name="save_location",
        description="Record where the vehicle is, after the caller says.",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": ("Road or street plus the nearest town or "
                                    "exit, in the caller's words."),
                }
            },
            "required": ["location"],
        },
    )
    def save_location(self, args, raw_data):
        location = (args.get("location") or "").strip()
        if len(location) < 6:
            return FunctionResult(
                "INCOMPLETE: that is not enough to find them. Ask for the "
                "road and the nearest town or exit."
            )
        r = FunctionResult(f"Location saved: {location}.")
        r.add_action("set_global_data", {"location": location})
        return r

    @AgentBase.tool(
        name="save_vehicle",
        description="Record the vehicle's make, model and colour.",
        parameters={
            "type": "object",
            "properties": {
                "vehicle": {
                    "type": "string",
                    "description": "Make, model and colour, in the caller's words.",
                }
            },
            "required": ["vehicle"],
        },
    )
    def save_vehicle(self, args, raw_data):
        vehicle = (args.get("vehicle") or "").strip()
        if len(vehicle.split()) < 2:
            return FunctionResult(
                "INCOMPLETE: need at least make and colour. Ask again."
            )
        r = FunctionResult(f"Vehicle saved: {vehicle}.")
        r.add_action("set_global_data", {"vehicle": vehicle})
        return r

    @AgentBase.tool(
        name="save_problem",
        description="Record what is wrong with the vehicle.",
        parameters={
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": "What happened, in the caller's words.",
                }
            },
            "required": ["problem"],
        },
    )
    def save_problem(self, args, raw_data):
        problem = (args.get("problem") or "").strip()
        if not problem:
            return FunctionResult("INCOMPLETE: ask what happened.")
        # Nothing is dispatched here. A real line would hand the three saved
        # fields to its dispatch system; this one records them.
        r = FunctionResult(
            f"Problem saved: {problem}. Tell the caller the request is recorded."
        )
        r.add_action("set_global_data", {"problem": problem})
        return r


agent = ClaimIntakeAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
