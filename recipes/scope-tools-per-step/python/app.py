"""Scope an agent's tools per step.

Each step declares exactly which functions exist while it is active. A tool the
step does not list is not withheld from the model - it is not presented at all.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase
from signalwire.core.function_result import FunctionResult

# the SDK does not read .env for you
load_dotenv()


class IntakeAgent(AgentBase):
    def __init__(self):
        super().__init__(name="intake", route="/intake")

        self.prompt_add_section(
            "Role",
            "You take a caller's name, then find out why they are calling, "
            "then route them. Follow the current step and nothing else.",
        )

        contexts = self.define_contexts()
        flow = contexts.add_context("default")

        # Step one: save_name is the only function that exists here.
        flow.add_step("collect_name") \
            .add_section("Current Task", "Ask for the caller's full name.") \
            .set_step_criteria("The caller has given a name.") \
            .set_functions(["save_name"]) \
            .set_valid_steps(["collect_reason"])

        # Step two: transferring becomes possible only now.
        flow.add_step("collect_reason") \
            .add_section("Current Task",
                         "Ask why they are calling, then route them.") \
            .set_step_criteria("The caller has explained why they called.") \
            .set_functions(["save_reason", "transfer_to_human"]) \
            .set_valid_steps(["collect_reason"])

    @AgentBase.tool(
        name="save_name",
        description="Record the caller's name",
        parameters={
            "name": {
                "type": "string",
                "description": "The caller's full name",
            }
        },
    )
    def save_name(self, args, raw_data):
        name = (args.get("name") or "").strip()
        if not name:
            return FunctionResult("I did not catch that - could you repeat it?")
        result = FunctionResult(f"Thank you {name}.")
        # Carry it forward without routing it back through the model.
        result.add_action("set_global_data", {"caller_name": name})
        return result

    @AgentBase.tool(
        name="save_reason",
        description="Record why the caller is calling",
        parameters={
            "reason": {
                "type": "string",
                "description": "Why the caller is calling, in their words",
            }
        },
    )
    def save_reason(self, args, raw_data):
        reason = (args.get("reason") or "").strip()
        result = FunctionResult("Got it.")
        result.add_action("set_global_data", {"intake_reason": reason})
        return result

    @AgentBase.tool(
        name="transfer_to_human",
        description="Connect the caller to a human agent",
        parameters={},
    )
    def transfer_to_human(self, args, raw_data):
        # connect() emits the documented shape: a SWML action carrying the
        # connect verb, plus "transfer": "true" so the agent exits. A bare
        # {"connect": ...} action is not in the platform's SWAIG action list.
        return FunctionResult("Connecting you now.").connect(
            os.environ["SUPPORT_ADDRESS"], final=True
        )


if __name__ == "__main__":
    IntakeAgent().serve(port=int(os.getenv("PORT", "8080")))
