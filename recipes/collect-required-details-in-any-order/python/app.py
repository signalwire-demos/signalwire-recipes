"""Collect required details in any order.

A caller reporting an absence gives the details in whatever order they come
to mind. One tool, `record_detail`, takes a field name and a value and writes
it into `global_data`; the handler answers with what is still missing. A
second tool, `submit_report`, reads the collected details from the request
body and refuses until every required field is present. The prompt asks; the
handlers keep the checklist.

Written against signalwire-sdk 3.0.1.
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# The checklist. Order here is the order the model is offered, nothing more:
# the caller may fill it in any order.
REQUIRED = {"employee_name": "the employee's name",
            "shift_date": "the date of the shift",
            "reason": "the reason for the absence"}
OPTIONAL = {"expected_return": "when they expect to be back",
            "notes": "anything else for the manager"}
FIELDS = {**REQUIRED, **OPTIONAL}

# Your HR system. A real one is an API call.
REPORTS = []


def _text(value):
    """The model may send a number where a string was asked for."""
    return "" if value is None else str(value).strip()


def missing(details):
    """The required fields not yet recorded, in checklist order."""
    return [f for f in REQUIRED if not _text(details.get(f))]


def status_line(details):
    gaps = missing(details)
    if gaps:
        return "Still needed: " + ", ".join(REQUIRED[f] for f in gaps) + "."
    return ("Everything required is recorded. Read the details back to the caller, "
            "then call submit_report.")


class AbsenceLine(AgentBase):
    def __init__(self):
        super().__init__(name="absence-line", route="/absence")
        self.prompt_add_section(
            "Role",
            "You take absence reports for a warehouse. Callers give details in any "
            "order; record each one as soon as you hear it. Never ask for something "
            "already recorded. When the tool says everything required is in, read "
            "the details back and submit.",
        )

    @AgentBase.tool(
        name="record_detail",
        description=("Record one detail of the absence report as soon as the caller "
                     "says it, in any order. Call it once per detail."),
        parameters={
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": list(FIELDS),
                          "description": "Which detail this is."},
                "value": {"type": "string",
                          "description": "The detail in the caller's words."},
            },
            "required": ["field", "value"],
        },
    )
    def record_detail(self, args, raw_data):
        field = _text(args.get("field"))
        value = _text(args.get("value"))
        if field not in FIELDS:
            # the enum shapes what the model is offered; the handler decides
            return FunctionResult(f"UNKNOWN_FIELD: {field!r} is not on the report. "
                                  f"Record one of: {', '.join(FIELDS)}.")
        if not value:
            return FunctionResult(f"EMPTY: nothing to record for {FIELDS[field]}. "
                                  "Ask the caller again.")
        details = dict((raw_data.get("global_data") or {}).get("details") or {})
        details[field] = value
        # set_global_data merges top-level keys, so the whole details object
        # goes back, not one field of it
        result = FunctionResult(f"Recorded {FIELDS[field]}. {status_line(details)}")
        result.update_global_data({"details": details})
        return result

    @AgentBase.tool(
        name="submit_report",
        description=("File the absence report. Only call this after the tool has said "
                     "everything required is recorded."),
        parameters={"type": "object", "properties": {}},
    )
    def submit_report(self, args, raw_data):
        global_data = raw_data.get("global_data") or {}
        if global_data.get("report_id"):
            # a retry, or the model asking twice: one report per call
            return FunctionResult(f"ALREADY_FILED: {global_data['report_id']}. Tell the "
                                  "caller the reference.")
        details = global_data.get("details") or {}
        gaps = missing(details)
        if gaps:
            # the model asked to submit early; the checklist says no
            return FunctionResult("MISSING: " + ", ".join(REQUIRED[f] for f in gaps)
                                  + ". Ask for those before submitting.")
        report_id = f"ABS-{len(REPORTS) + 1001}"
        REPORTS.append({"id": report_id, **details,
                        "filed_at": datetime.now(timezone.utc).isoformat()})
        result = FunctionResult(
            f"Report {report_id} filed for {details['employee_name']}, "
            f"shift {details['shift_date']}. Tell the caller the reference and end "
            "the call.")
        result.update_global_data({"report_id": report_id})
        return result


agent = AbsenceLine()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
