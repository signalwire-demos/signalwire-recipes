"""Prove the claim without a network.

Claim: four call commands share one control id. `calling.record` starts a
recording with documented audio params and an optional `status_url`;
`calling.record.pause` carries a `behavior` from the spec's enum;
`calling.record.resume` and `calling.record.stop` name the same control id.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. The
required lists, the audio params, the format and direction enums and the pause
behavior enum are read from the vendored spec. The TypeScript surface goes
through the same recorder seam and is held to the same expected bodies, so the
two surfaces are compared against this file rather than against each other.
Expected values live here, not in app.py.
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
CONTROL = "agent-desk-recording"
STATUS = "https://desk.example.com/recording-events"
AUDIO = {"stereo": True, "direction": "both", "format": "mp3", "max_length": 0,
         "initial_timeout": 0, "end_silence_timeout": 0, "terminators": ""}
# what the REST command applies when those three are left out
PROMPT_DEFAULTS = {"initial_timeout": 4, "end_silence_timeout": 0.5, "terminators": "#"}
# what SWML's whole-call verb uses instead, in the bundled schema
WHOLE_CALL_DEFAULTS = {"initial_timeout": 0, "end_silence_timeout": 0, "terminators": ""}


def variant(command):
    """Top-level required, params required and params properties, from the spec."""
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
            return v.get("required", []), params.get("required", []), props, deref
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    for helper, args in [(recipe.start, (CALL, STATUS)), (recipe.pause, (CALL,)),
                         (recipe.resume, (CALL,)), (recipe.stop, (CALL,)),
                         (recipe.start, (CALL,))]:
        before = len(rec.calls)
        helper(*args)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    # calling.record: control_id and record.audio are required; every audio key,
    # the format and the direction are documented
    top, required, props, deref = variant("calling.record")
    assert set(top) == {"command", "id", "params"}, top
    assert set(required) == {"control_id", "record"}, required
    record = props["record"]
    assert record["required"] == ["audio"], record
    audio = deref(record["properties"]["audio"])
    unknown = set(AUDIO) - set(audio["properties"])
    assert not unknown, f"undocumented audio params: {sorted(unknown)}"
    formats = deref(audio["properties"]["format"])["enum"]
    directions = deref(audio["properties"]["direction"])["enum"]
    assert AUDIO["format"] in formats, (AUDIO["format"], formats)
    assert AUDIO["direction"] in directions, (AUDIO["direction"], directions)
    assert "status_url" in props, sorted(props)

    # the three the recipe sets on purpose: left out, the command stops the
    # recording the way a voice prompt stops
    rest_defaults = {k: deref(audio["properties"][k]).get("default")
                     for k in PROMPT_DEFAULTS}
    assert rest_defaults == PROMPT_DEFAULTS, rest_defaults
    # SWML's whole-call verb defaults them to what this recipe sends
    record_call = V.swml_schema()["$defs"]["RecordCall"]["properties"]["record_call"]
    swml_defaults = {k: record_call["properties"][k].get("default")
                     for k in WHOLE_CALL_DEFAULTS}
    assert swml_defaults == WHOLE_CALL_DEFAULTS, swml_defaults
    assert {k: AUDIO[k] for k in WHOLE_CALL_DEFAULTS} == WHOLE_CALL_DEFAULTS, AUDIO

    # calling.record.pause: behavior is one of the spec's two values
    top, required, props, _ = variant("calling.record.pause")
    assert required == ["control_id"], required
    behaviors = props["behavior"]["enum"]
    assert set(behaviors) == {"skip", "silence"}, behaviors
    assert rec.calls[1]["body"]["params"]["behavior"] in behaviors

    for command in ("calling.record.resume", "calling.record.stop"):
        top, required, props, _ = variant(command)
        assert set(top) == {"command", "id", "params"}, top
        assert required == ["control_id"], (command, required)

    expected = [
        {"command": "calling.record", "id": CALL,
         "params": {"control_id": CONTROL, "record": {"audio": AUDIO},
                    "status_url": STATUS}},
        {"command": "calling.record.pause", "id": CALL,
         "params": {"control_id": CONTROL, "behavior": "silence"}},
        {"command": "calling.record.resume", "id": CALL,
         "params": {"control_id": CONTROL}},
        {"command": "calling.record.stop", "id": CALL,
         "params": {"control_id": CONTROL}},
        # without a status_url the key is absent, not null
        {"command": "calling.record", "id": CALL,
         "params": {"control_id": CONTROL, "record": {"audio": AUDIO}}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, props, _ = variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"

    # the TypeScript surface: the same helpers, the same recorder seam, held to
    # the expected bodies above
    node = V.node_surface(HERE, CALL, STATUS)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 5, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = "typescript sends the same five bodies"

    print(f"ok: five POST {PATH} for id {CALL[:8]}...: record with documented stereo "
          f"mp3 audio params and a status_url, pause with behavior silence, resume, "
          f"stop, each body naming control_id {CONTROL}; the three prompt-style "
          f"defaults ({PROMPT_DEFAULTS['initial_timeout']}s, "
          f"{PROMPT_DEFAULTS['end_silence_timeout']}s, "
          f"{PROMPT_DEFAULTS['terminators']}) are overridden with the values SWML's "
          f"record_call uses; no status_url means no key; {ts_note}")


if __name__ == "__main__":
    main()
