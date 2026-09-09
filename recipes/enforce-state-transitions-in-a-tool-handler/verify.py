"""Prove the claim without a network.

Claim: the handler, not the model, decides whether a transition is legal, and an
illegal request is refused with a reason.

Proof: the rendered SWML shows the step graph the model sees. Running the
handlers shows the same tool call producing a transition or a refusal purely
from collected state, and the transition arrives under the JSON key the platform
reads, `change_step`, not the SDK method name that produced it.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


def actions(result):
    return result.get("action", [])


def main():
    V.sdk_banner()
    from app import SERVICEABLE, BookingAgent

    agent = BookingAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    steps = {s["name"]: s for s in ai["prompt"]["contexts"]["default"]["steps"]}

    # Listing "schedule" in valid_steps would hand the model a next_step
        # straight past the handler. Leaving it empty removes that tool, but it
        # is not a lock: the runtime still advances on step criteria, which is
    # why start_scheduling and confirm_slot both re-check the state below.
    assert steps["identify_bike"]["valid_steps"] == [], steps
    assert "schedule" not in steps["identify_bike"]["valid_steps"], steps
    assert steps["identify_bike"]["functions"] == ["record_bike",
                                                   "start_scheduling"], steps
    assert steps["schedule"]["functions"] == ["confirm_slot"], steps

    # An unserviceable bike is refused and writes nothing.
    r = agent._execute_swaig_function("record_bike", {"bike_type": "unicycle"},
                                      call_id="c1")
    assert r["response"].startswith("UNSUPPORTED"), r
    assert not actions(r), r

    # A serviceable one is recorded by code, under the platform's key.
    r = agent._execute_swaig_function("record_bike", {"bike_type": " Gravel "},
                                      call_id="c1")
    assert actions(r) == [{"set_global_data": {"bike_type": "gravel"}}], r

    # The model asks to move on before anything was recorded. Refused.
    r = agent._execute_swaig_function("start_scheduling", {}, call_id="c1",
                                      raw_data={"global_data": {}})
    assert r["response"].startswith("NOT_READY"), r
    assert not actions(r), r

    # Refused again when the state is present but not serviceable, so the
    # check is on the value and not merely on the key existing.
    r = agent._execute_swaig_function(
        "start_scheduling", {}, call_id="c1",
        raw_data={"global_data": {"bike_type": "unicycle"}})
    assert r["response"].startswith("NOT_READY"), r
    assert not actions(r), r

    # With real state, the transition is emitted.
    r = agent._execute_swaig_function(
        "start_scheduling", {}, call_id="c1",
        raw_data={"global_data": {"bike_type": "gravel"}})
    # swml_change_step() is the SDK method; change_step is what is sent.
    assert actions(r) == [{"change_step": "schedule"}], r
    assert "swml_change_step" not in json.dumps(r), r

    # A step is not a boundary: the booking tool refuses on its own state,
    # however the call arrived at the step that exposes it.
    r = agent._execute_swaig_function("confirm_slot", {"slot": "Thursday 9am"},
                                      call_id="c1", raw_data={"global_data": {}})
    assert r["response"].startswith("NOT_READY"), r
    r = agent._execute_swaig_function(
        "confirm_slot", {"slot": "Thursday 9am"}, call_id="c1",
        raw_data={"global_data": {"bike_type": "gravel"}})
    assert "Booked a gravel" in r["response"], r

    print(f"ok: start_scheduling and confirm_slot both refuse until one of "
          f"{sorted(SERVICEABLE)} is recorded; the transition arrives as "
          f"change_step, and reaching a step buys nothing on its own")


if __name__ == "__main__":
    main()
