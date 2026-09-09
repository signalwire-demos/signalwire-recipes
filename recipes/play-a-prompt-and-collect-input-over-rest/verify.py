"""Prove the claim without a network.

Claim: `calling.play` speaks text or plays a file into a live call by control
id, `calling.play.stop` cuts it short, and `calling.collect` gathers digits or
speech whose result the platform delivers to `status_url`. A collect with no
status URL is refused before any request is made.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. A
play is sent with and without its optional `status_url`, so the branch the
README shows is exercised both ways. The required lists, each play item's own
required param, the digits and speech properties and the collect description's
delivery rule are all read from the vendored spec. The TypeScript surface goes
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
PLAY = "agent-desk-prompt"
COLLECT = "agent-desk-input"
STATUS = "https://desk.example.com/collect-events"
TEXT = "Please key in your account number, then press pound."
URL = "https://desk.example.com/hold.mp3"
VOLUME = -6


def variant(command):
    """Description, top-level required, params required and properties."""
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
            # the spec wraps its descriptions, so compare on one line
            desc = " ".join(v.get("description", "").split())
            return (desc, v.get("required", []),
                    params.get("required", []), props, deref)
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # a volume outside the documented range, or one that is not a number at
    # all, never reaches the wire. The command line hands over a string, so the
    # bad values are the strings a person would actually type
    for bad, expected_message in [(41, "-40 and 40"), ("41", "-40 and 40"),
                                  ("loud", "must be a number"),
                                  (None, "must be a number")]:
        try:
            recipe.set_volume(CALL, bad)
        except ValueError as exc:
            assert expected_message in str(exc), (bad, exc)
        else:
            raise AssertionError(f"volume {bad!r} was sent")

    # a collect with no status_url never reaches the wire, missing or empty
    for bad in (None, ""):
        for helper in (recipe.ask_digits, recipe.ask_speech):
            try:
                helper(CALL, bad)
            except ValueError as exc:
                assert "status_url" in str(exc), exc
            else:
                raise AssertionError(f"{helper.__name__} sent a collect with no status_url")
    assert rec.calls == [], rec.calls

    for helper, args, kwargs in [
            (recipe.say, (CALL, TEXT), {}),
            (recipe.say, (CALL, TEXT), {"status_url": STATUS}),
            (recipe.play_file, (CALL, URL), {}),
            (recipe.set_volume, (CALL, str(VOLUME)), {}),
            (recipe.stop_playback, (CALL,), {}),
            (recipe.ask_digits, (CALL, STATUS), {}),
            (recipe.ask_speech, (CALL, STATUS), {}),
            (recipe.stop_collect, (CALL,), {})]:
        before = len(rec.calls)
        helper(*args, **kwargs)
        assert len(rec.calls) == before + 1, (helper.__name__, rec.calls)

    # calling.play: control_id and play are required; a tts item requires text,
    # an audio item requires url, and both types are in the spec's enum
    desc, top, required, props, deref = variant("calling.play")
    assert set(top) == {"command", "id", "params"}, top
    assert set(required) == {"control_id", "play"}, required
    items = [deref(alt) for alt in deref(props["play"]["items"])["oneOf"]]
    types = deref(items[0]["properties"]["type"])["enum"]
    assert set(types) == {"audio", "tts", "silence", "ringtone"}, types
    # by item, not by set: a reversed association must fail here
    required_by_item = {i["title"]: deref(i["properties"]["params"])["required"]
                        for i in items}
    assert required_by_item["Calling.PlayTtsItem"] == ["text"], required_by_item
    assert required_by_item["Calling.PlayAudioItem"] == ["url"], required_by_item
    assert required_by_item["Calling.PlaySilenceItem"] == ["duration"], required_by_item
    for state in ("playing", "paused", "finished", "error"):
        assert state in desc, (state, desc)

    desc, top, required, props, _ = variant("calling.play.stop")
    assert required == ["control_id"], required

    # calling.play.volume: both params required, and the range is in the text
    desc, top, required, props, _ = variant("calling.play.volume")
    assert set(required) == {"control_id", "volume"}, required
    span = " ".join(props["volume"]["description"].split())
    assert "Must be between -40 and 40" in span, span

    # calling.collect: control_id is the only required param; digits needs max;
    # the description says results are delivered by webhook, not in the response
    desc, top, required, props, deref = variant("calling.collect")
    assert set(top) == {"command", "id", "params"}, top
    assert required == ["control_id"], required
    assert "delivered asynchronously via the `status_url` webhook" in desc, desc
    assert "At least one of `digits` or `speech` must be provided" in desc, desc
    digits, speech = props["digits"], props["speech"]
    assert digits["required"] == ["max"], digits
    # the clock does not start on its own: the spec's default is false
    assert props["start_input_timers"].get("default") is False, props["start_input_timers"]
    # found by what they carry, so inserting a request cannot silently move them
    collects = [c["body"]["params"] for c in rec.calls
                if c["body"]["command"] == "calling.collect"]
    sent_digits = [p for p in collects if "digits" in p][0]["digits"]
    sent_speech = [p for p in collects if "speech" in p][0]["speech"]
    assert not set(sent_digits) - set(digits["properties"]), sent_digits
    assert not set(sent_speech) - set(speech["properties"]), sent_speech

    desc, top, required, props, _ = variant("calling.collect.stop")
    assert required == ["control_id"], required

    expected = [
        {"command": "calling.play", "id": CALL,
         "params": {"control_id": PLAY,
                    "play": [{"type": "tts", "params": {"text": TEXT}}]}},
        # the optional branch: a status_url is carried, and absent above
        {"command": "calling.play", "id": CALL,
         "params": {"control_id": PLAY,
                    "play": [{"type": "tts", "params": {"text": TEXT}}],
                    "status_url": STATUS}},
        {"command": "calling.play", "id": CALL,
         "params": {"control_id": PLAY,
                    "play": [{"type": "audio", "params": {"url": URL}}]}},
        # a number on the wire, whatever the caller passed in
        {"command": "calling.play.volume", "id": CALL,
         "params": {"control_id": PLAY, "volume": float(VOLUME)}},
        {"command": "calling.play.stop", "id": CALL, "params": {"control_id": PLAY}},
        {"command": "calling.collect", "id": CALL,
         "params": {"control_id": COLLECT, "initial_timeout": 10,
                    "digits": {"max": 10, "terminators": "#", "digit_timeout": 5},
                    "start_input_timers": True, "status_url": STATUS}},
        {"command": "calling.collect", "id": CALL,
         "params": {"control_id": COLLECT, "initial_timeout": 10,
                    "speech": {"end_silence_timeout": 1.5, "speech_timeout": 15,
                               "language": "en-US"},
                    "start_input_timers": True, "status_url": STATUS}},
        {"command": "calling.collect.stop", "id": CALL,
         "params": {"control_id": COLLECT}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, _, props, _ = variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"

    # the TypeScript surface: the same helpers, the same recorder seam, held to
    # the expected bodies above
    node = V.node_surface(HERE, CALL, TEXT, URL, STATUS)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["beforeAnyRequest"] == 0, node["beforeAnyRequest"]
        assert len(node["refused"]) == 6, node["refused"]
        assert all("status_url" in r for r in node["refused"][:4]), node["refused"]
        assert "-40 and 40" in node["refused"][4], node["refused"]
        assert "must be a number" in node["refused"][5], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 8, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = ("typescript sends the same eight bodies and refuses both a "
                   "collect with no status_url, an out-of-range volume and one "
                   "that is not a number")

    print(f"ok: eight POST {PATH} for id {CALL[:8]}...: play tts with and without "
          f"a status_url, an audio item, play.stop, a digits collect and a speech "
          f"collect with documented fields, collect.stop; each item type is pinned to "
          f"its own required param, a volume inside the documented range, both "
          f"collects start the input timers the spec "
          f"defaults to false, and a collect with no status_url is refused before "
          f"any request; {ts_note}")


if __name__ == "__main__":
    main()
