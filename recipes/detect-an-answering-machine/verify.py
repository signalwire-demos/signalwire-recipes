"""Prove the claim without a network.

Claim: an outbound call is classified human, machine or fax before your logic
runs, and the message waits for the beep.

Proof: the document placed with the call runs `detect_machine` before anything
that speaks, branches on `detect_result` using only documented values, and sets
`detect_message_end` so detection holds until a greeting finishes. The request
itself is the documented dial, and the document validates against the SWML
schema.
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
    "SIGNALWIRE_PHONE_NUMBER": "+15550001111",
    "PUBLIC_URL": "https://recipes.example.test",
})

import verifylib as V  # noqa: E402

# documented detect_result values, lowercase
DOCUMENTED = {"machine", "human", "fax", "unknown", "detecting", "error"}


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.call("+15552223333")

    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    assert (call["method"], call["path"]) == ("POST", "/api/calling/calls"), call
    params = call["body"]["params"]
    schema = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    assert set(params) <= set(schema["properties"]), sorted(params)

    doc = params["swml"]
    V.validate_swml(doc)
    names = V.verb_names(doc)

    # "before your logic runs": nothing speaks until the classification is in.
    assert names.index("detect_machine") < names.index("switch"), names
    assert "play" not in names[:names.index("detect_machine")], names

    dm = V.first(doc, "detect_machine")
    # "waits for the beep"
    assert dm["detect_message_end"] is True, dm
    assert "amd" in dm["detectors"] and "fax" in dm["detectors"], dm
    assert dm["initial_timeout"] > 0 and dm["end_silence_timeout"] > 0, dm
    assert dm["status_url"].endswith("/amd-status"), dm

    sw = V.first(doc, "switch")
    assert sw["variable"] == "detect_result", sw

    # Only documented values, and the three the claim names are all handled.
    assert set(sw["case"]) <= DOCUMENTED, sorted(set(sw["case"]) - DOCUMENTED)
    assert {"human", "machine", "fax"} <= set(sw["case"]), sorted(sw["case"])

    # A fax gets no message; a human and a machine both do.
    fax = sw["case"]["fax"]
    assert fax == [{"hangup": {}}], fax
    for who in ("human", "machine"):
        said = sw["case"][who][0]["play"]["url"]
        assert said.startswith("say:") and recipe.MESSAGE in said, (who, said)
    # No branch may offer a keypress: this document collects no digits.
    assert "prompt" not in V.verb_names(doc), V.verb_names(doc)
    for branch in list(sw["case"].values()) + [sw["default"]]:
        for verb in branch:
            said = verb.get("play", {}).get("url", "")
            assert "press" not in said.lower(), said

    # The unclassified outcomes get the bare message: no keypress offer, and
    # nothing that only makes sense to a person.
    assert sw["default"], sw
    default_said = sw["default"][0]["play"]["url"]
    assert recipe.MESSAGE in default_said, sw["default"]
    assert "press" not in default_said.lower(), default_said
    for value in recipe.UNKNOWN:
        assert value not in sw["case"], value

    print(f"ok: detect_machine(detectors={dm['detectors']}, "
          f"detect_message_end=True) before any play; switch on detect_result "
          f"handles {sorted(sw['case'])} plus a default")


if __name__ == "__main__":
    main()
