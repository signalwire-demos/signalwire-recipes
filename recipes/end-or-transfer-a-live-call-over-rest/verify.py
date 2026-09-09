"""Prove the claim without a network.

Claim: each helper sends one documented call command addressed to the call id:
`calling.end` with a reason from the spec's enum, `calling.transfer` with the
required `dest`, and `calling.disconnect` with no params.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. The
reason enum, the transfer `dest` requirement and its accepted forms, and the
empty disconnect params are all read from the vendored spec, not assumed. Every
documented reason reaches the wire and the default is `hangup`, so narrowing the
guard fails here. A reason outside the enum is refused before any request is
made. The spec's command table is read for the sentence the README makes about
each command. The TypeScript surface goes through the same recorder seam and is
held to the same expected bodies, so the two surfaces are compared against this
file rather than against each other. Expected values live here, not in app.py.
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
DEST = "sip:tier2@pbx.example.com"
REASONS = ["hangup", "cancel", "busy", "noAnswer", "decline", "error"]
DEFAULT_REASON = "hangup"
# what the spec's own command table says each command does
TABLE = {
    "calling.end": "Terminate an active call immediately",
    "calling.transfer": "Transfer a call to a new destination (SIP URI, phone "
                        "number, or inline SWML)",
    "calling.disconnect": "Disconnect bridged calls without hanging up either leg",
}


def documented_variant(command):
    """The command's required list and params schema, read from the spec."""
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
            props = {k: deref(v) for k, v in params.get("properties", {}).items()}
            return variant.get("required", []), params.get("required", []), props
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # a reason outside the enum never reaches the wire
    try:
        recipe.hang_up(CALL, "rejected")
    except ValueError as exc:
        assert "rejected" in str(exc), exc
    else:
        raise AssertionError("an undocumented reason was sent")
    assert rec.calls == [], rec.calls

    for helper, args in [(recipe.hang_up, (CALL, "busy")),
                         (recipe.transfer, (CALL, DEST)),
                         (recipe.unbridge, (CALL,))]:
        before = len(rec.calls)
        helper(*args)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    # calling.end: the reason is one of the spec's enum values
    top, _, props = documented_variant("calling.end")
    assert set(top) == {"command", "id", "params"}, top
    reasons = props["reason"]["enum"]
    assert set(reasons) == set(REASONS), reasons
    assert set(recipe.END_REASONS) == set(REASONS), recipe.END_REASONS
    assert rec.calls[0]["body"]["params"]["reason"] in reasons, rec.calls[0]["body"]

    # every documented reason reaches the wire, so a narrowed guard fails here,
    # and the default is the one the recipe ships
    every = V.Recorder()
    recipe.client.calling._http = every
    for reason in REASONS:
        recipe.hang_up(CALL, reason)
    recipe.hang_up(CALL)
    assert [c["body"] for c in every.calls] == [
        {"command": "calling.end", "id": CALL, "params": {"reason": r}}
        for r in REASONS + [DEFAULT_REASON]], [c["body"] for c in every.calls]
    recipe.client.calling._http = rec

    # calling.transfer: dest is required and accepts a string or an inline object
    top, required, props = documented_variant("calling.transfer")
    assert set(top) == {"command", "id", "params"}, top
    assert required == ["dest"], required
    forms = {alt["type"] for alt in props["dest"]["oneOf"]}
    assert forms == {"string", "object"}, forms
    assert isinstance(rec.calls[1]["body"]["params"]["dest"], str)

    # calling.disconnect: the spec documents no params at all
    top, required, props = documented_variant("calling.disconnect")
    assert set(top) == {"command", "id", "params"}, top
    assert props == {} and not required, (props, required)

    expected = [
        {"command": "calling.end", "id": CALL, "params": {"reason": "busy"}},
        {"command": "calling.transfer", "id": CALL, "params": {"dest": DEST}},
        {"command": "calling.disconnect", "id": CALL, "params": {}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, props = documented_variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"

    # the README says what each command does to the call; the spec's command
    # table is where that sentence comes from
    table = V.spec("rest")["paths"][PATH]["post"]["description"]
    rows = dict(
        (cells[1].strip().strip("`"), cells[2].strip())
        for line in table.splitlines() if line.startswith("|")
        for cells in [line.split("|")] if len(cells) > 3)
    for command, says in TABLE.items():
        assert rows.get(command) == says, (command, rows.get(command))

    # the TypeScript surface: the same helpers, the same recorder seam, held to
    # the expected bodies above
    node = V.node_surface(HERE, CALL, DEST)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["reasons"] == REASONS, node["reasons"]
        assert len(node["refused"]) == 1 and "rejected" in node["refused"][0], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 3, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        assert [c["body"] for c in node["every"]] == [
            {"command": "calling.end", "id": CALL, "params": {"reason": r}}
            for r in REASONS + [DEFAULT_REASON]], node["every"]
        # the spec's dest is a string or an object; the typescript surface
        # takes both, and the object form is sent here
        inline = {"version": "1.0.0", "sections": {"main": [{"hangup": {}}]}}
        assert [c["body"] for c in node["inline"]] == [
            {"command": "calling.transfer", "id": CALL,
             "params": {"dest": inline}}], node["inline"]
        ts_note = ("typescript sends the same three bodies, refuses the same "
                   "reason, and transfers to an inline SWML dest")

    print(f"ok: three POST {PATH} for id {CALL[:8]}...: calling.end with an enum "
          f"reason, calling.transfer with a required dest, calling.disconnect with "
          f"empty params; all six reasons and the {DEFAULT_REASON} default reach "
          f"the wire, an undocumented one is refused before any request, and the "
          f"spec's command table says what the README says it says; {ts_note}")


if __name__ == "__main__":
    main()
