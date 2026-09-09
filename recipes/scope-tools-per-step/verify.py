"""Prove the claim without a network.

Claim: at each step of the conversation the model can only see the tools that
step lists.

Proof: construct the agent, render the SWML the platform would receive, and
assert the per-step `functions` whitelists in `ai.prompt.contexts`. Then run the
tool handlers locally and assert the JSON keys the platform receives - not the
SDK method names that produced them.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "python"))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "tools"))

import verifylib as V  # noqa: E402
os.environ.setdefault("SUPPORT_ADDRESS", "sip:support@example.sip.signalwire.com")

import signalwire  # noqa: E402
from app import IntakeAgent  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


def main():
    print(f"sdk {signalwire.__version__} at {signalwire.__file__}")
    agent = IntakeAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]

    steps = {
        s["name"]: s for s in ai["prompt"]["contexts"]["default"]["steps"]
    }
    # The claim, in the platform's own terms.
    assert steps["collect_name"]["functions"] == ["save_name"], steps["collect_name"]
    assert "transfer_to_human" not in steps["collect_name"]["functions"]
    assert steps["collect_reason"]["functions"] == ["save_reason", "transfer_to_human"]
    assert steps["collect_name"]["valid_steps"] == ["collect_reason"]

    # All three tools exist at the agent level; the step decides visibility.
    names = [f["function"] for f in ai["SWAIG"]["functions"]]
    assert names == ["save_name", "save_reason", "transfer_to_human"], names

    # Handler output: assert the JSON keys, not the SDK method names.
    r = agent._execute_swaig_function("save_name", {"name": "Dana Whitfield"}, call_id="c1")
    assert r["action"] == [{"set_global_data": {"caller_name": "Dana Whitfield"}}], r

    r = agent._execute_swaig_function("save_name", {"name": "  "}, call_id="c1")
    assert "action" not in r, r  # an empty name writes nothing

    r = agent._execute_swaig_function("transfer_to_human", {}, call_id="c1")
    (action,) = r["action"]
    assert action["transfer"] == "true", action
    assert action["SWML"]["sections"]["main"] == [
        {"connect": {"to": os.environ["SUPPORT_ADDRESS"]}}
    ], action

    print("ok: collect_name exposes", steps["collect_name"]["functions"],
          "| collect_reason exposes", steps["collect_reason"]["functions"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
