"""Prove the claim without a network.

Claim: the tool returns an allowlisted projection, so withheld fields are absent
from the model's context rather than forbidden by prompt.

Proof: run the tool handler exactly as the platform would (function name, args,
raw call data) and assert that the response text - the only thing the model
receives - contains every exposed field and none of the hidden ones. Then render
the SWML and assert the tool is declared and the prompt carries no field names.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "python"))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "tools"))

import verifylib as V  # noqa: E402

import signalwire  # noqa: E402
from app import EXPOSED, AccountAgent, load_customer  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")

HIDDEN = {"risk_score", "margin_pct", "internal_notes", "card_last_four", "last_name"}


def main():
    print(f"sdk {signalwire.__version__} at {signalwire.__file__}")
    agent = AccountAgent()
    V.assert_basic_auth_from_env(agent)

    raw = {"call_id": "c1", "caller_id_num": "+15551234567"}
    r = agent._execute_swaig_function("get_account", {}, call_id="c1", raw_data=raw)
    assert set(r.keys()) == {"response"}, r  # no actions; just data for the model
    seen = json.loads(r["response"])

    full = load_customer("+15551234567")
    assert HIDDEN <= set(full), "the fixture must contain the fields being hidden"
    assert set(seen) == set(EXPOSED), seen
    assert not (set(seen) & HIDDEN), seen
    # The values are the record's own, not redacted placeholders.
    for k in EXPOSED:
        assert seen[k] == full[k], (k, seen[k], full[k])

    doc = json.loads(agent._render_swml())
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    assert [f["function"] for f in ai["SWAIG"]["functions"]] == ["get_account"]
    prompt = json.dumps(ai["prompt"])
    for k in HIDDEN:
        assert k not in prompt, f"prompt mentions hidden field {k}"

    print(f"ok: model sees {sorted(seen)}; never sees {sorted(HIDDEN)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
