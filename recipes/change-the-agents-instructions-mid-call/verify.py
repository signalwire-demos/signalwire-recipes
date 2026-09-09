"""Prove the claim without a network.

Claim: a tool result carries a `context_switch` action that replaces the
system prompt on the call in progress, with the earlier turns either
summarised in or dropped, and no result carries a transfer.

Proof: run each handler and compare the whole function result to the exact
payload the platform receives. The key is `context_switch`, not the SDK method
name. It carries an object with `system_prompt` plus `consolidate` (summarise)
or `full_reset` (drop). Every result is then walked recursively for `SWML`,
`transfer` and `connect`, so no key anywhere in it moves the call. The rendered
document still validates against the bundled schema.
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

# Expected payloads live here, not imported from app.py. Each is the complete
# function result, so a stray key fails the comparison.
BILLING = (
    "You are now the billing specialist for Ridgeline Cycles. The caller has "
    "already been identified. Answer questions about invoices, refunds and "
    "payment dates. Do not discuss repairs or parts."
)
WORKSHOP = (
    "You are now the workshop coordinator for Ridgeline Cycles. Book, move "
    "or check repair appointments. Do not discuss billing."
)
FRONT_DESK = (
    "You answer the phone for a bicycle shop. Find out whether the caller "
    "needs billing or the workshop, then hand over using the matching tool. "
    "Do not answer their question yourself."
)

EXPECTED = {
    "become_billing": {
        "response": "Switching you to billing.",
        "action": [{"context_switch": {"system_prompt": BILLING, "consolidate": True}}],
    },
    "become_workshop": {
        "response": "Switching you to the workshop.",
        "action": [{"context_switch": {"system_prompt": WORKSHOP, "consolidate": True}}],
    },
    "start_over": {
        "response": "Starting over.",
        "action": [{"context_switch": {"system_prompt": FRONT_DESK, "full_reset": True}}],
    },
}
MOVES_THE_CALL = {"SWML", "transfer", "connect"}


def keys_anywhere(node, found=None):
    """Every dict key at any depth of a result."""
    found = set() if found is None else found
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(k)
            keys_anywhere(v, found)
    elif isinstance(node, list):
        for v in node:
            keys_anywhere(v, found)
    return found


def main():
    V.sdk_banner()
    from signalwire import FunctionResult
    from app import FrontDeskAgent

    agent = FrontDeskAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    names = sorted(f["function"] for f in ai["SWAIG"]["functions"])
    assert names == sorted(EXPECTED), names
    # start_over restores the prompt the call opened with
    role = next(s for s in ai["prompt"]["pom"] if s["title"] == "Role")
    assert role["body"] == FRONT_DESK, role

    for tool, want in EXPECTED.items():
        got = agent._execute_swaig_function(tool, {}, call_id="c1")
        # checked before the exact comparison, so each can fail on its own:
        # nothing in the result, at any depth, moves the call elsewhere
        assert not (keys_anywhere(got) & MOVES_THE_CALL), (tool, keys_anywhere(got))
        # the object form: the schema documents context_switch as an object
        assert isinstance(got["action"][0]["context_switch"], dict), got
        # then the whole payload, not a field of it
        assert got == want, (tool, json.dumps(got, indent=1))

    # system_prompt alone emits the bare-string shorthand, which is why every
    # switch above passes consolidate or full_reset
    bare = FunctionResult("x").switch_context(system_prompt="p").to_dict()
    assert bare["action"] == [{"context_switch": "p"}], bare

    print(f"ok: {list(EXPECTED)} each emit exactly one context_switch object "
          f"with the expected system_prompt; two consolidate, one full_reset "
          f"back to the opening prompt; no key at any depth is SWML, transfer "
          f"or connect; system_prompt alone emits a bare string")


if __name__ == "__main__":
    main()
