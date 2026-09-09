"""Prove the claim without a network.

Claim: `calling.live_translate` takes one `action`, and the spec's four are
`start`, `inject`, `summarize` and `stop`. Start requires `from_lang`, `to_lang`
and `direction`; inject requires `message` and `direction` from the two-value
enum; summarize requires nothing; stop is the bare action.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. The
four action variants, their required lists, the direction enum shared by start's
array and inject's string, and the speech engine enum are read from the vendored
spec. A direction outside the enum is refused before any request. The TypeScript
surface goes through the same recorder seam and is held to the same expected
bodies. Expected values live here, not in app.py.
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
FROM_LANG, TO_LANG = "en-US", "es-ES"
DIRECTIONS = ["remote-caller", "local-caller"]
EVENTS = "https://desk.example.com/translation-events"
SUMMARY = "https://desk.example.com/summary"
MESSAGE = "A supervisor is joining."


def bits():
    """The live_translate variant, its four action schemas, and the deref."""
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for v in schemas["Calling.CallRequest"]["oneOf"]:
        cmd = deref(v["properties"]["command"])
        if "calling.live_translate" in (cmd.get("enum") or []):
            params = deref(v["properties"]["params"])
            props = {k: deref(x) for k, x in params["properties"].items()}
            actions = {a["title"]: a for a in
                       (deref(alt) for alt in props["action"]["oneOf"])}
            return params.get("required", []), props, actions, deref
    raise AssertionError("calling.live_translate is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # a direction outside the enum never reaches the wire
    try:
        recipe.say(CALL, MESSAGE, "supervisor")
    except ValueError as exc:
        assert "direction must be one of" in str(exc), exc
    else:
        raise AssertionError("an undocumented direction was sent")
    assert rec.calls == [], rec.calls

    for helper, args in [(recipe.start, (CALL, FROM_LANG, TO_LANG, EVENTS)),
                         (recipe.say, (CALL, MESSAGE)),
                         (recipe.summary, (CALL, SUMMARY)),
                         (recipe.stop, (CALL,))]:
        before = len(rec.calls)
        helper(*args)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    required, props, actions, deref = bits()
    assert required == ["action"], required
    assert set(actions) == {"Calling.LiveTranslateStartAction",
                            "Calling.LiveTranslateSummarizeAction",
                            "Calling.LiveTranslateInjectAction",
                            "Calling.LiveTranslateStopAction"}, sorted(actions)
    said = " ".join(props["action"]["description"].split())
    assert said == ("The translation action to perform: start, stop, summarize, "
                    "or inject."), said

    start = deref(actions["Calling.LiveTranslateStartAction"]["properties"]["start"])
    assert set(start["required"]) == {"from_lang", "to_lang", "direction"}, start["required"]
    per_side = deref(deref(start["properties"]["direction"])["items"])["enum"]
    assert per_side == DIRECTIONS, per_side
    assert list(recipe.DIRECTIONS) == DIRECTIONS, recipe.DIRECTIONS
    engines = deref(start["properties"]["speech_engine"])["enum"]
    assert set(engines) == {"deepgram", "google"}, engines

    inject = deref(actions["Calling.LiveTranslateInjectAction"]["properties"]["inject"])
    assert set(inject["required"]) == {"message", "direction"}, inject["required"]
    # the same two values, as a single string rather than an array
    assert deref(inject["properties"]["direction"])["enum"] == DIRECTIONS

    summarize = deref(
        actions["Calling.LiveTranslateSummarizeAction"]["properties"]["summarize"])
    assert not summarize.get("required"), summarize.get("required")
    assert {"webhook", "prompt"} <= set(summarize["properties"]), summarize["properties"]

    expected = [
        {"command": "calling.live_translate", "id": CALL,
         "params": {"action": {"start": {"from_lang": FROM_LANG, "to_lang": TO_LANG,
                                         "direction": DIRECTIONS,
                                         "speech_engine": "deepgram",
                                         "live_events": True,
                                         "webhook": EVENTS}}}},
        {"command": "calling.live_translate", "id": CALL,
         "params": {"action": {"inject": {"message": MESSAGE,
                                          "direction": "remote-caller"}}}},
        {"command": "calling.live_translate", "id": CALL,
         "params": {"action": {"summarize": {"webhook": SUMMARY}}}},
        {"command": "calling.live_translate", "id": CALL,
         "params": {"action": {"stop": {}}}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        assert set(want["params"]) <= set(props), sorted(want["params"])

    # every key the recipe sends inside an action is a documented property
    inner = {"start": start, "inject": inject, "summarize": summarize}
    for want in expected:
        (name, body), = want["params"]["action"].items()
        if name == "stop":
            continue
        unknown = set(body) - set(inner[name]["properties"])
        assert not unknown, f"undocumented {name} keys: {sorted(unknown)}"

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, CALL, FROM_LANG, TO_LANG, EVENTS, MESSAGE, SUMMARY)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["refused"]) == 1, node["refused"]
        assert "direction must be one of" in node["refused"][0], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 4, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = "typescript sends the same four actions and refuses the same direction"

    print(f"ok: four POST {PATH} for id {CALL[:8]}...: calling.live_translate with "
          f"start ({FROM_LANG} to {TO_LANG}, both directions, deepgram), inject, "
          f"summarize and stop, each matching one of the spec's four action variants "
          f"and its required list; an undocumented direction is refused before any "
          f"request; {ts_note}")


if __name__ == "__main__":
    main()
