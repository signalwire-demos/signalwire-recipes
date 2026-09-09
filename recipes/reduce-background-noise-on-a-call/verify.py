"""Prove the claim without a network.

Claim: noise reduction is switched on for a leg and off again, in SWML with
`denoise` and `stop_denoise`, and mid-call over REST with the commands
`calling.denoise` and `calling.denoise.stop`.

Proof: both SWML surfaces validate against the bundled schema and run the
same verbs in the same order, `denoise` before the recording and `stop_denoise`
after it. Both verbs carry an empty object, because the schema gives them no
parameters. With a fresh recorder attached for each helper, `quiet` and `loud`
each make exactly one POST to the documented calling path. Each body carries
the command, the call id at the top level and empty params, which is what the
spec's variants require. Expected values live here, not in app.py.
"""
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
ORDER = ["answer", "denoise", "play", "record", "stop_denoise", "play", "hangup"]


def variant(command):
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for v in schemas["Calling.CallRequest"]["oneOf"]:
        if command in (deref(v["properties"]["command"]).get("enum") or []):
            return v.get("required", []), deref(v["properties"]["params"])
    raise AssertionError(f"{command} is not a documented call command")


def check(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ORDER, (label, V.verb_names(doc))
    assert V.first(doc, "denoise") == {} and V.first(doc, "stop_denoise") == {}, label
    # the schema gives both verbs no parameters
    schema = V.swml_schema()["$defs"]
    for verb in ("Denoise", "StopDenoise"):
        props = list(schema[verb]["properties"].values())[0]
        assert props["properties"] == {} and props["unevaluatedProperties"] == {"not": {}}, verb


def main():
    V.sdk_banner()
    import app as recipe
    py = recipe.build().get_document()
    check(py, "python")
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    check(y, "yaml")
    assert py == y, "python and yaml surfaces differ"

    calls = []
    for helper, command in ((recipe.quiet, "calling.denoise"),
                            (recipe.loud, "calling.denoise.stop")):
        rec = V.Recorder()  # a fresh recorder per helper: one helper, one request
        recipe.client.calling._http = rec
        helper(CALL)
        assert len(rec.calls) == 1, (helper.__name__, rec.calls)
        calls.append((rec.calls[0], command))
    for call, command in calls:
        assert (call["method"], call["path"]) == ("POST", PATH), call
        assert call["body"] == {"command": command, "id": CALL, "params": {}}, call["body"]
        V.assert_documented("rest", "POST", PATH, None)
        required, params = variant(command)
        assert set(required) == {"command", "id", "params"}, (command, required)
        assert params.get("properties", {}) == {}, (command, params)

    print(f"ok: both surfaces run {ORDER} with parameterless denoise/stop_denoise; "
          f"quiet() and loud() POST calling.denoise and calling.denoise.stop for id "
          f"{CALL[:8]}... with empty params, as the spec's variants require")


if __name__ == "__main__":
    main()
