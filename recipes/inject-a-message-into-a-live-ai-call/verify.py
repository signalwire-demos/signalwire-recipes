"""Prove the claim without a network.

Claim: each helper sends one documented `calling.ai_message` command, with the
call id at the top level and exactly the params the spec describes: a system
message, a `global_data` merge, or a `reset`.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path. Every body equals the expected shape. The
params, including the nested `reset` keys, are all documented properties of
the spec's `calling.ai_message` variant, and the role is one of its enum
values. Expected values live here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
CALL = "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f"


def documented_variant(command):
    """The command's params schema, read from the spec rather than assumed."""
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for variant in schemas["Calling.CallRequest"]["oneOf"]:
        cmd = deref(variant["properties"]["command"])
        if command in (cmd.get("enum") or []):
            params = deref(variant["properties"]["params"])
            return variant.get("required", []), {
                k: deref(v) for k, v in params["properties"].items()}
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    for helper, arg in [(recipe.nudge, "The caller is a returning customer. Skip the "
                                       "identity questions."),
                        (recipe.share, {"tier": "gold"}),
                        (recipe.restart, "You are now the billing specialist.")]:
        before = len(rec.calls)
        helper(CALL, arg)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    required, props = documented_variant("calling.ai_message")
    assert set(required) == {"command", "id", "params"}, required
    roles = props["role"]["enum"]
    assert set(roles) == {"system", "user", "assistant"}, roles
    # the observed role is checked on its own, before the exact comparison
    assert rec.calls[0]["body"]["params"]["role"] in roles, rec.calls[0]["body"]

    expected_params = [
        {"role": "system", "message_text": "The caller is a returning customer. "
                                           "Skip the identity questions."},
        {"global_data": {"tier": "gold"}},
        {"reset": {"full_reset": True, "system_prompt": "You are now the billing "
                                                        "specialist."}},
    ]
    for call, want in zip(rec.calls, expected_params):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        body = call["body"]
        # the command, the call id at the top level, and exactly these params
        assert body == {"command": "calling.ai_message", "id": CALL, "params": want}, \
            json.dumps(body, indent=1)
        unknown = set(want) - set(props)
        assert not unknown, f"undocumented ai_message params: {sorted(unknown)}"
        # nested objects too: reset's keys against the spec's reset schema
        for key, value in want.items():
            if isinstance(value, dict) and props[key].get("properties"):
                nested = set(value) - set(props[key]["properties"])
                assert not nested, f"undocumented {key} keys: {sorted(nested)}"

    print(f"ok: three POST {PATH} calling.ai_message for id {CALL[:8]}...: a system "
          f"message, a global_data merge and a full reset, every param documented")


if __name__ == "__main__":
    main()
