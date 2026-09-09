"""Prove the claim without a network.

Claim: data written to global_data by one agent is read by the next agent after
the transfer; nothing is re-asked and nothing is serialised into the transfer URL.

Proof: render both agents' SWML and assert (1) both opt in to
`params.persist_global_data`, the documented mechanism that restores global_data
when a new AI session starts on the same call; (2) the intake tool's result
carries a `set_global_data` action with the collected fields and a `SWML`
transfer to the billing agent whose URL contains none of them; (3) the billing
prompt references the same global_data keys.
"""
import json
import os
import pathlib
import sys

os.environ.setdefault("PUBLIC_URL", "https://recipes.example.test")
sys.path.insert(0, str(pathlib.Path(__file__).parent / "python"))

import signalwire  # noqa: E402
from app import BillingAgent, IntakeAgent, PUBLIC_URL  # noqa: E402


def ai_verb(agent):
    doc = json.loads(agent._render_swml())
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def main():
    print(f"sdk {signalwire.__version__} at {signalwire.__file__}")
    intake, billing = IntakeAgent(), BillingAgent()
    a_in, a_bill = ai_verb(intake), ai_verb(billing)

    for a in (a_in, a_bill):
        assert a["params"]["persist_global_data"] is True, a["params"]
        assert a["params"]["transfer_summary"] is True, a["params"]

    r = intake._execute_swaig_function(
        "route_caller", {"name": "Dana Whitfield", "reason": "a charge I do not recognise"},
        call_id="c1")
    assert r["post_process"] is True, r  # speak first, then transfer
    actions = r["action"]
    assert actions[0] == {"set_global_data": {
        "caller_name": "Dana Whitfield",
        "intake_reason": "a charge I do not recognise",
        "verified": True}}, actions[0]
    swml = actions[1]
    assert swml["transfer"] == "true", swml
    (verb,) = swml["SWML"]["sections"]["main"]
    dest = verb["transfer"]["dest"]
    assert dest == f"{PUBLIC_URL}/billing-specialist", dest
    for leaked in ("Dana", "Whitfield", "charge", "recognise", "verified"):
        assert leaked not in dest, f"context serialised into the transfer URL: {leaked}"

    # An incomplete intake writes nothing and transfers nowhere.
    r = intake._execute_swaig_function("route_caller", {"name": "Dana"}, call_id="c1")
    assert "action" not in r, r

    prompt = json.dumps(a_bill["prompt"])
    for key in ("${global_data.caller_name}", "${global_data.intake_reason}"):
        assert key in prompt, f"billing prompt does not read {key}"

    print("ok: set_global_data + SWML transfer to", dest, "| persist_global_data on both agents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
