"""Prove the claim without a network.

Claim: account tools do not exist in the model's tool list until a verification
tool has succeeded.

Proof: in the rendered SWML the account functions carry `active: false` and
`verify_pin` does not; a wrong PIN produces no action; the right PIN produces a
`toggle_functions` action that activates exactly the account tools and retires
verify_pin. Keys asserted are the platform's, not the SDK method names.
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


def main():
    V.sdk_banner()
    from app import ACCOUNT_TOOLS, BankAgent
    agent = BankAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fns = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert set(fns) == {"verify_pin", *ACCOUNT_TOOLS}, set(fns)
    for name in ACCOUNT_TOOLS:
        assert fns[name].get("active") is False, (name, fns[name])
    assert fns["verify_pin"].get("active", True) is True, fns["verify_pin"]

    raw = {"call_id": "c1", "caller_id_num": "+15551234567"}
    r = agent._execute_swaig_function("verify_pin", {"pin": "0000"}, call_id="c1", raw_data=raw)
    assert "action" not in r, r  # wrong PIN: nothing unlocks

    r = agent._execute_swaig_function("verify_pin", {"pin": "4242"}, call_id="c1", raw_data=raw)
    toggles = [a["toggle_functions"] for a in r["action"] if "toggle_functions" in a]
    on = {t["function"] for grp in toggles for t in grp if t["active"] is True}
    off = {t["function"] for grp in toggles for t in grp if t["active"] is False}
    assert on == set(ACCOUNT_TOOLS), on
    assert off == {"verify_pin"}, off
    assert {"set_global_data": {"verified": True}} in r["action"], r["action"]

    # Unknown caller with the right digits still fails: the check is code.
    r = agent._execute_swaig_function("verify_pin", {"pin": "4242"}, call_id="c2",
                                      raw_data={"call_id": "c2", "caller_id_num": "+15550000000"})
    assert "action" not in r, r
    print(f"ok: {ACCOUNT_TOOLS} render active:false; correct PIN -> toggle_functions on them, off verify_pin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
