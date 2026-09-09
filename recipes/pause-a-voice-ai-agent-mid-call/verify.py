"""Prove the claim without a network.

Claim: `calling.ai_hold` holds the caller with a spoken prompt and a timeout the
spec requires as a numeric string; `calling.ai_unhold` brings the agent back
with no params; `calling.ai.stop` ends the AI and is what the SDK's `ai_stop`
method sends.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. The
timeout is a string on the wire, not an integer, which is what the spec's own
description demands. The reserved `control_id` on `calling.ai.stop` is read from
the spec and deliberately not sent. The TypeScript surface goes through the same
recorder seam and is held to the same expected bodies. Expected values live
here, not in app.py.
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
SECONDS = 90
PROMPT = "Let me check that for you. One moment."


def variant(command):
    """Params required and properties, plus the deref, from the spec."""
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for v in schemas["Calling.CallRequest"]["oneOf"]:
        cmd = deref(v["properties"]["command"])
        if command in (cmd.get("enum") or []):
            params = deref(v["properties"]["params"])
            props = {k: deref(x) for k, x in params.get("properties", {}).items()}
            return v.get("required", []), params.get("required", []), props
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # a fractional hold is refused before it is sent
    try:
        recipe.hold(CALL, 1.5)
    except ValueError as exc:
        assert "whole number" in str(exc), exc
    else:
        raise AssertionError("a fractional timeout was sent")
    assert rec.calls == [], rec.calls

    for helper, args in [(recipe.hold, (CALL, SECONDS)), (recipe.unhold, (CALL,)),
                         (recipe.stop, (CALL,))]:
        before = len(rec.calls)
        helper(*args)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    # calling.ai_hold: the spec types timeout as a string and says so twice
    top, required, props = variant("calling.ai_hold")
    assert set(top) == {"command", "id", "params"}, top
    assert not required, required
    assert props["timeout"]["type"] == "string", props["timeout"]
    said = " ".join(props["timeout"]["description"].split())
    assert "must be sent as a string" in said, said
    assert "integer payloads are rejected" in said, said
    assert "prompt" in props, sorted(props)

    # what the recipe sent is a string, and it is the seconds it was given
    sent = rec.calls[0]["body"]["params"]["timeout"]
    assert isinstance(sent, str) and sent == str(SECONDS), repr(sent)

    top, required, props = variant("calling.ai_unhold")
    assert set(top) == {"command", "id", "params"}, top
    assert props == {} and not required, (props, required)

    # calling.ai.stop documents one param and calls it reserved, so it is not sent
    top, required, props = variant("calling.ai.stop")
    assert set(top) == {"command", "id", "params"}, top
    reserved = " ".join(props["control_id"]["description"].split())
    assert reserved.startswith("Reserved field"), reserved
    assert "currently ignored" in reserved, reserved
    assert rec.calls[2]["body"]["params"] == {}, rec.calls[2]

    expected = [
        {"command": "calling.ai_hold", "id": CALL,
         "params": {"timeout": str(SECONDS), "prompt": PROMPT}},
        {"command": "calling.ai_unhold", "id": CALL, "params": {}},
        # the method is ai_stop; the documented command has a dot
        {"command": "calling.ai.stop", "id": CALL, "params": {}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, props = variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, CALL, str(SECONDS))
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["refused"]) == 1, node["refused"]
        assert "whole number" in node["refused"][0], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 3, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        assert isinstance(node["captured"][0]["body"]["params"]["timeout"], str)
        ts_note = "typescript sends the same three bodies, with a string timeout"

    print(f"ok: three POST {PATH} for id {CALL[:8]}...: calling.ai_hold with a prompt "
          f"and timeout \"{SECONDS}\" as the string the spec demands, calling.ai_unhold "
          f"with no params, and calling.ai.stop, which is what the SDK's ai_stop "
          f"method sends; the reserved control_id is not sent, and a fractional "
          f"timeout is refused before any request; {ts_note}")


if __name__ == "__main__":
    main()
