"""Prove the claim without a network.

Claim: `calling.detect` starts detection on a live call by control id, with a
`detect` object whose `type` is `machine`, `fax` or `digit`, and the result is
delivered to `status_url`. A detect with no status URL is refused before any
request. `calling.detect.stop` ends it by the same control id.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. The
three config variants, the type enum, the fax tone enum, the machine parameter
defaults and the delivery rule in the command's own description are all read
from the vendored spec. The TypeScript surface goes through the same recorder
seam and is held to the same expected bodies, so the two surfaces are compared
against this file rather than against each other. Expected values live here,
not in app.py.
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
CONTROL = "screening"
STATUS = "https://dialer.example.com/detect-events"
TYPES = ["machine", "fax", "digit"]
# what the spec applies to a machine detect when they are left out
MACHINE_DEFAULTS = {"initial_timeout": 4.5, "end_silence_timeout": 1,
                    "machine_voice_threshold": 1.25, "machine_words_threshold": 6,
                    "detect_interruptions": False, "detect_message_end": True}


def variant(command):
    """Description, required lists and params properties, from the spec."""
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
            desc = " ".join(v.get("description", "").split())
            return desc, params.get("required", []), props, deref, schemas
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # a detect with no status_url never reaches the wire, missing or empty
    for bad in (None, ""):
        for helper in (recipe.machine, recipe.fax, recipe.digits):
            try:
                helper(CALL, bad)
            except ValueError as exc:
                assert "status_url" in str(exc), exc
            else:
                raise AssertionError(f"{helper.__name__} sent a detect with no status_url")
    assert rec.calls == [], rec.calls

    for helper, args in [(recipe.machine, (CALL, STATUS)), (recipe.fax, (CALL, STATUS)),
                         (recipe.digits, (CALL, STATUS)), (recipe.stop, (CALL,))]:
        before = len(rec.calls)
        helper(*args)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    desc, required, props, deref, schemas = variant("calling.detect")
    assert set(required) == {"control_id", "detect"}, required
    assert "delivered via the `status_url` webhook" in desc, desc
    assert "runs asynchronously up to `timeout` seconds" in desc, desc

    # the three configs the detect object is a oneOf of, and their shared enum
    configs = [deref(alt) for alt in props["detect"]["oneOf"]]
    titles = {c["title"] for c in configs}
    assert titles == {"Calling.DetectMachineConfig", "Calling.DetectFaxConfig",
                      "Calling.DetectDigitConfig"}, titles
    for config in configs:
        assert config["required"] == ["type"], config["title"]
        assert deref(config["properties"]["type"])["enum"] == TYPES, config["title"]
    assert recipe.TYPES == tuple(TYPES), recipe.TYPES

    # the machine parameters the recipe sets are documented, and the defaults
    # it leaves alone are what the spec says they are
    by_title = {c["title"]: deref(c["properties"]["params"]) for c in configs}
    machine_params = by_title["Calling.DetectMachineConfig"]["properties"]
    defaults = {k: deref(v).get("default") for k, v in machine_params.items()
                if k in MACHINE_DEFAULTS}
    assert defaults == MACHINE_DEFAULTS, defaults
    tones = deref(by_title["Calling.DetectFaxConfig"]["properties"]["tone"])["enum"]
    assert set(tones) == {"CNG", "CED", "cng", "ced"}, tones
    assert "digits" in by_title["Calling.DetectDigitConfig"]["properties"]

    desc, required, props, _, _ = variant("calling.detect.stop")
    assert required == ["control_id"], required

    expected = [
        {"command": "calling.detect", "id": CALL,
         "params": {"control_id": CONTROL, "timeout": 30, "status_url": STATUS,
                    "detect": {"type": "machine",
                               "params": {"machine_voice_threshold": 1.25,
                                          "machine_words_threshold": 6,
                                          "detect_message_end": True}}}},
        {"command": "calling.detect", "id": CALL,
         "params": {"control_id": CONTROL, "timeout": 30, "status_url": STATUS,
                    "detect": {"type": "fax", "params": {"tone": "CED"}}}},
        {"command": "calling.detect", "id": CALL,
         "params": {"control_id": CONTROL, "timeout": 30, "status_url": STATUS,
                    "detect": {"type": "digit",
                               "params": {"digits": "0123456789"}}}},
        {"command": "calling.detect.stop", "id": CALL,
         "params": {"control_id": CONTROL}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, props, _, _ = variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"
        sent = want["params"].get("detect")
        if sent:
            allowed = by_title[{"machine": "Calling.DetectMachineConfig",
                                "fax": "Calling.DetectFaxConfig",
                                "digit": "Calling.DetectDigitConfig"}[sent["type"]]]
            unknown = set(sent["params"]) - set(allowed["properties"])
            assert not unknown, f"undocumented {sent['type']} params: {sorted(unknown)}"

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, CALL, STATUS)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["refused"]) == 6, node["refused"]
        assert all("status_url" in r for r in node["refused"]), node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 4, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = ("typescript sends the same four bodies and refuses a detect "
                   "with no status_url")

    print(f"ok: four POST {PATH} for id {CALL[:8]}...: machine, fax and digit detects "
          f"on control_id {CONTROL}, each with a documented config and the "
          f"{TYPES} type enum, then detect.stop; the spec's machine defaults are "
          f"{MACHINE_DEFAULTS['machine_voice_threshold']} and "
          f"{MACHINE_DEFAULTS['machine_words_threshold']}; a detect with no "
          f"status_url is refused before any request; {ts_note}")


if __name__ == "__main__":
    main()
