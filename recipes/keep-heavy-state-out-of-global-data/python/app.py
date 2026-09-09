"""Keep heavy state out of global_data.

`global_data` travels with every tool call and is visible to the model. It is
the right place for a short, AI-facing summary and the wrong place for a
growing record. This agent keeps the record server-side, keyed by `call_id`,
and writes only a count and a one-line summary to `global_data`.

The tool handlers read the full record from the store, so the agent can still
read everything back on request, and the model carries none of it between
turns in `global_data`.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# The per-call record, keyed by call_id. A real store is a database row per
# call; a dict shows the shape.
STORE = {}

AREAS = ["brakes", "gears", "wheels", "frame", "lights"]


class InspectionAgent(AgentBase):
    def __init__(self):
        super().__init__(name="inspection", route="/inspection")
        self.prompt_add_section(
            "Role",
            "You take a bicycle inspection report over the phone. For each area "
            "the mechanic mentions, record the finding with record_finding. When "
            "they say they are done, use read_back_report and read it to them.",
        )

    @AgentBase.tool(
        name="record_finding",
        description="Record what the mechanic found in one area of the bike.",
        parameters={
            "type": "object",
            "properties": {
                "area": {"type": "string", "enum": AREAS},
                "detail": {"type": "string",
                           "description": "What they said, in full."},
            },
            "required": ["area", "detail"],
        },
    )
    def record_finding(self, args, raw_data):
        call_id = (raw_data or {}).get("call_id")
        area, detail = args.get("area"), (args.get("detail") or "").strip()
        if area not in AREAS or not detail:
            return FunctionResult("INVALID: name the area and say what was found.")
        # the full text goes to the store, under this call
        findings = STORE.setdefault(call_id, [])
        findings.append({"area": area, "detail": detail})
        # the model gets a count and the distinct areas, nothing more; the
        # areas field is bounded by the five areas however many findings arrive
        seen = list(dict.fromkeys(f["area"] for f in findings))
        r = FunctionResult(f"Recorded {area}. {len(findings)} findings so far.")
        r.add_action("set_global_data", {
            "findings": len(findings),
            "areas": ", ".join(seen),
        })
        return r

    @AgentBase.tool(
        name="read_back_report",
        description="Read the whole report back to the mechanic.",
        parameters={"type": "object", "properties": {}},
    )
    def read_back_report(self, args, raw_data):
        # read from the store, not from global_data
        findings = STORE.get((raw_data or {}).get("call_id"), [])
        if not findings:
            return FunctionResult("INCOMPLETE: nothing recorded yet.")
        lines = "; ".join(f"{f['area']}: {f['detail']}" for f in findings)
        return FunctionResult(f"Report with {len(findings)} findings. {lines}")


agent = InspectionAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
