"""Prove the claim without a network.

Claim: a caller can give the required details of a report in any order, and
the report cannot be filed until every required detail is present. The
checklist lives in the tool handlers, which read `global_data` from the request
body, not in the prompt.

Proof: render the document and assert both tools, the `field` enum equal to the
checklist, and a parameterless submit. Then run the handlers in a deliberately
scrambled order, threading `global_data` between calls the way the platform
does: each `record_detail` emits `set_global_data` carrying the whole details
object and names what is still missing; `submit_report` refuses with a MISSING
list at every incomplete stage and files once the list is empty. An unknown
field and an empty value are refused without an action. The TypeScript surface
runs the same sequence through its /swaig route and must produce the same
responses and actions. Expected values live here, not in either surface.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

USER, PASSWORD = "signalwire", "verify-only-password"
os.environ.setdefault("SWML_BASIC_AUTH_USER", USER)
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", PASSWORD)

FIELDS = ["employee_name", "shift_date", "reason", "expected_return", "notes"]
NAME, DATE, REASON = "Dana Whitfield", "Monday the eighth", "a fever"
UNKNOWN = ("UNKNOWN_FIELD: '%s' is not on the report. Record one of: "
           + ", ".join(FIELDS) + ".")
TWO_MISSING = ("MISSING: the employee's name, the date of the shift. Ask for those "
               "before submitting.")

# the scrambled order, and what each step must say and write; details grow
D1 = {"reason": REASON}
D2 = {**D1, "notes": "4471"}
D3 = {**D2, "shift_date": DATE}
D4 = {**D3, "employee_name": NAME}
STEPS = [
    # a value with stray spaces is trimmed before it is written
    ("record_detail", {"field": "reason", "value": "  a fever "},
     "Recorded the reason for the absence. Still needed: the employee's name, "
     "the date of the shift.", {"details": D1}),
    ("submit_report", {}, TWO_MISSING, None),
    # an optional field, and a number where a string was asked for
    ("record_detail", {"field": "notes", "value": 4471},
     "Recorded anything else for the manager. Still needed: the employee's name, "
     "the date of the shift.", {"details": D2}),
    ("submit_report", {}, TWO_MISSING, None),
    ("record_detail", {"field": "shift_date", "value": DATE},
     "Recorded the date of the shift. Still needed: the employee's name.",
     {"details": D3}),
    ("record_detail", {"field": "badge_number", "value": "4471"},
     UNKNOWN % "badge_number", None),
    # a prototype name is not a field either
    ("record_detail", {"field": "constructor", "value": "x"},
     UNKNOWN % "constructor", None),
    ("record_detail", {"field": "employee_name", "value": "  "},
     "EMPTY: nothing to record for the employee's name. Ask the caller again.", None),
    ("submit_report", {},
     "MISSING: the employee's name. Ask for those before submitting.", None),
    ("record_detail", {"field": "employee_name", "value": NAME},
     "Recorded the employee's name. Everything required is recorded. Read the details "
     "back to the caller, then call submit_report.", {"details": D4}),
    ("submit_report", {},
     f"Report ABS-1001 filed for {NAME}, shift {DATE}. Tell the caller the reference "
     "and end the call.", {"report_id": "ABS-1001"}),
    # asked again, or retried: one report per call
    ("submit_report", {},
     "ALREADY_FILED: ABS-1001. Tell the caller the reference.", None),
]


def check(results, label):
    """One pass over the scrambled sequence, for either surface."""
    assert len(results) == len(STEPS), (label, len(results))
    for (tool, args, said, written), got in zip(STEPS, results):
        assert got["response"] == said, (label, tool, args, got["response"])
        actions = got.get("action") or []
        if written is None:
            assert not actions, (label, tool, actions)
        else:
            assert actions == [{"set_global_data": written}], (label, tool, actions)


def main():
    V.sdk_banner()
    from app import AbsenceLine, REPORTS

    agent = AbsenceLine()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    funcs = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert sorted(funcs) == ["record_detail", "submit_report"], sorted(funcs)
    field = funcs["record_detail"]["parameters"]["properties"]["field"]
    assert field["enum"] == FIELDS, field
    assert funcs["record_detail"]["parameters"]["required"] == ["field", "value"]
    assert funcs["submit_report"]["parameters"]["properties"] == {}

    # thread global_data between calls the way the platform does
    global_data, results = {}, []
    for tool, args, _said, _written in STEPS:
        raw = {"call_id": "c1", "global_data": dict(global_data)}
        r = agent._execute_swaig_function(tool, dict(args), call_id="c1", raw_data=raw)
        for action in r.get("action") or []:
            if "set_global_data" in action:
                global_data.update(action["set_global_data"])
        results.append(r)
    check(results, "python")
    assert len(REPORTS) == 1 and REPORTS[0]["employee_name"] == NAME, REPORTS
    assert global_data["details"] == D4, global_data

    # the TypeScript surface, same sequence through its own route
    steps = json.dumps([{"tool": t, "args": a} for t, a, _s, _w in STEPS])
    node = V.node_surface(HERE, steps, env={"SWML_BASIC_AUTH_USER": USER,
                                            "SWML_BASIC_AUTH_PASSWORD": PASSWORD})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        V.validate_swml(node["doc"])
        tai = next(v for v in node["doc"]["sections"]["main"] if "ai" in v)["ai"]
        tfuncs = {f["function"]: f for f in tai["SWAIG"]["functions"]}
        assert sorted(tfuncs) == ["record_detail", "submit_report"], sorted(tfuncs)
        tparams = tfuncs["record_detail"]["parameters"]
        assert tparams["properties"]["field"]["enum"] == FIELDS, tparams
        assert tparams["required"] == ["field", "value"], tparams
        assert tfuncs["submit_report"]["parameters"]["properties"] == {}
        check(node["results"], "typescript")
        assert node["reports"] == 1, node["reports"]
        assert node["globalData"]["report_id"] == "ABS-1001", node["globalData"]
        assert node["globalData"]["details"] == D4, node["globalData"]
        ts_note = ("typescript renders the same tools and its /swaig route gives the "
                   "same twelve responses and actions")

    print(f"ok: record_detail offers {FIELDS} and writes the whole details object; "
          f"given reason, a note, date, name in that order, submit_report refuses three "
          f"times with the exact missing list, files ABS-1001 once the list is empty, "
          f"and answers ALREADY_FILED after; unknown fields (including 'constructor'), "
          f"an empty value and a numeric value are handled the same on both surfaces; "
          f"{ts_note}")


if __name__ == "__main__":
    main()
