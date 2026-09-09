"""Transfer a call without losing context.

Intake writes what it learned to global_data; the platform persists global_data
across AI sessions on the same call (persist_global_data); the receiving agent
reads it in its prompt on the first turn. Nothing is serialised into the transfer
URL.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, AgentServer, FunctionResult

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8080")


class ContextCarryingAgent(AgentBase):
    """Both agents opt in to the same platform behaviour."""

    def __init__(self, **kw):
        super().__init__(**kw)
        # global_data is saved to a channel variable when this AI session ends
        # and restored when the next AI session starts on the same call.
        self.set_param("persist_global_data", True)
        # Also hand the next agent a summary of the conversation so far.
        self.set_param("transfer_summary", True)


class IntakeAgent(ContextCarryingAgent):
    def __init__(self):
        super().__init__(name="intake", route="/intake")
        self.prompt_add_section(
            "Role",
            "Collect the caller's name and the reason for their call, then use "
            "route_caller to hand them to billing.",
        )

    @AgentBase.tool(
        name="route_caller",
        description="Record the caller's name and reason, then route to billing",
        parameters={
            "name": {"type": "string", "description": "The caller's full name"},
            "reason": {"type": "string", "description": "Why they are calling"},
        },
    )
    def route_caller(self, args, raw_data):
        name = (args.get("name") or "").strip()
        reason = (args.get("reason") or "").strip()
        if not name or not reason:
            return FunctionResult("I still need your name and the reason for your call.")
        result = FunctionResult(f"Thanks {name}, connecting you to billing.",
                                post_process=True)
        # Written into the call's global_data from the handler - the model does
        # not relay it, and the transfer URL carries none of it.
        result.update_global_data(
            {"caller_name": name, "intake_reason": reason, "verified": True}
        )
        # Hand the call to the billing agent's SWML. The documented action shape
        # is a SWML document plus a sibling "transfer": "true" that exits this
        # agent for good - the same shape FunctionResult.connect() emits.
        # (FunctionResult.execute_swml(transfer=True) in sdk 3.0.1 puts the
        # transfer flag inside the document instead, so it is built by hand.)
        result.action.append({
            "SWML": {
                "version": "1.0.0",
                "sections": {"main": [
                    {"transfer": {"dest": f"{PUBLIC_URL}/billing-specialist"}}]},
            },
            "transfer": "true",
        })
        return result


class BillingAgent(ContextCarryingAgent):
    def __init__(self):
        super().__init__(name="billing", route="/billing-specialist")
        # The receiving agent reads context that already exists on the call.
        self.prompt_add_section(
            "Context",
            "You are speaking with ${global_data.caller_name}. They already "
            "explained: ${global_data.intake_reason}. They are already verified. "
            "Do not ask for their name or their reason again.",
        )
        self.prompt_add_section("Role", "Resolve the caller's billing question.")


def build_server(port=None):
    server = AgentServer(port=port or int(os.getenv("PORT", "8080")))
    server.register(IntakeAgent(), "/intake")
    server.register(BillingAgent(), "/billing-specialist")
    return server


if __name__ == "__main__":
    build_server().run()
