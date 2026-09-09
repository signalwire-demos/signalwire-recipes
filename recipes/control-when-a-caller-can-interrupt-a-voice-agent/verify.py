"""Prove the claim without a network.

Claim: when a caller may interrupt the agent, and when the agent decides the
caller has finished, are settings in `ai.params`, each bounded by the schema.

Proof: the rendered document carries exactly the eleven configured keys with the
configured values, and validates. The schema's bounds are read and asserted
and then exercised at the edge: 249 ms and 100 words are refused, 250 ms and 99
are accepted, and a document with a misspelt key validates, which is why the
exact-key assertion is the guard. The parsers are checked against a table of
raw environment strings, because `ENABLE_BARGE=false` has to reach the document
as the boolean the reference documents, `ENERGY_LEVEL=52.5` is a legal number,
and a typo has to stop the process rather than ship. The TypeScript surface
renders the same params, the same variants and the same parses.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

USER, PASSWORD = "signalwire", "verify-only-password"
os.environ.setdefault("SWML_BASIC_AUTH_USER", USER)
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", PASSWORD)
os.environ["BARGE_MIN_WORDS"] = "4"          # one value moved off its default

GREETING = "Ridgeline Cycles, how can I help?"
EXPECTED = {
    "static_greeting": GREETING,
    "enable_barge": "complete,partial", "barge_min_words": 4, "transparent_barge": True,
    "interrupt_on_noise": False, "static_greeting_no_barge": True,
    "end_of_speech_timeout": 700, "first_word_timeout": 1000,
    "speech_event_timeout": 1400, "energy_level": 52, "enable_turn_detection": True,
}
BOUNDS = {"barge_min_words": (1, 99), "end_of_speech_timeout": (250, 10000),
          "first_word_timeout": (0, 10000), "speech_event_timeout": (0, 10000),
          "energy_level": (0, 100)}
# the schema states a default for these; for the other two it states none
DEFAULTS = {"enable_barge": "complete,partial", "end_of_speech_timeout": 700,
            "first_word_timeout": 1000, "speech_event_timeout": 1400,
            "energy_level": 52, "static_greeting_no_barge": False,
            "transparent_barge": True, "enable_turn_detection": True}
NO_DEFAULT = ["barge_min_words", "interrupt_on_noise"]
# (override, must it validate?), each one step outside or on the bound
VARIANTS = [({"barge_min_words": 100}, False), ({"end_of_speech_timeout": 249}, False),
            ({"barge_min_words": 99, "end_of_speech_timeout": 250}, True),
            ({"energy_level": 52.5}, True),
            ({"enable_barge": False}, True),
            ({"enable_barg": "complete"}, True)]
# raw environment strings, and what each parser must make of them
BARGES = [("false", False), (" FALSE ", False), ("true", True),
          ("complete,partial", "complete,partial"), ("all", "all")]
NUMBERS = [("52", 52), ("52.5", 52.5), ("", 52)]
BAD_INTS = ["", "abc", "3.5"]
BAD_EXPECTED = [3, "threw", "threw"]


def ai_of(doc):
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def validates(doc):
    try:
        V.validate_swml(doc)
        return True
    except Exception:
        return False


def check(doc, variants, label):
    V.validate_swml(doc)
    params = ai_of(doc)["params"]
    assert params == EXPECTED, (label, params)
    # the greeting the platform speaks, not an instruction to the model
    assert params["static_greeting"] == GREETING, (label, params)
    prompt = ai_of(doc)["prompt"]
    rendered = str(prompt.get("pom") or prompt.get("text") or "")
    assert GREETING not in rendered, (label, rendered[:200])
    assert len(variants) == len(VARIANTS), (label, len(variants))
    for (override, ok), variant in zip(VARIANTS, variants):
        assert validates(variant) is ok, (label, override)
        got = ai_of(variant)["params"]
        assert got == {**EXPECTED, **override}, (label, override, got)


def check_parses(barge, number, bad_int, label):
    assert barge == [want for _raw, want in BARGES], (label, barge)
    assert number == [want for _raw, want in NUMBERS], (label, number)
    assert bad_int == BAD_EXPECTED, (label, bad_int)


def main():
    V.sdk_banner()
    import app as recipe

    V.assert_basic_auth_from_env(recipe.agent)
    doc = recipe.render()
    variants = [recipe.render({**recipe.TURN_TAKING, **o}) for o, _ok in VARIANTS]
    check(doc, variants, "python")

    def attempt(raw):
        try:
            return recipe.int_value(raw, 3)
        except ValueError:
            return "threw"

    check_parses([recipe.barge_value(raw) for raw, _ in BARGES],
                 [recipe.number_value(raw, 52) for raw, _ in NUMBERS],
                 [attempt(raw) for raw in BAD_INTS], "python")
    # a whole number stays an integer, so both surfaces render the same document
    assert isinstance(recipe.number_value("52", 52), int), recipe.number_value("52", 52)

    # the schema's bounds and defaults, read rather than remembered
    props = V.swml_schema()["$defs"]["AIParams"]["properties"]
    for key, (low, high) in BOUNDS.items():
        bounds = (props[key]["minimum"], props[key]["maximum"])
        assert bounds == (low, high), (key, props[key])
    for key, value in DEFAULTS.items():
        assert props[key]["default"] == value, (key, props[key])
    for key in NO_DEFAULT:
        assert "default" not in props[key], (key, props[key])
    # static_greeting_no_barge protects this line, which is why the greeting is
    # a param rather than a prompt section
    assert "always play at the beginning of the call" in \
        props["static_greeting"]["description"], props["static_greeting"]
    assert "static greeting will not be interrupted" in \
        props["static_greeting_no_barge"]["description"]
    # enable_barge takes a string or a boolean, which is why false is parsed
    types = {b.get("type") for b in props["enable_barge"]["anyOf"]}
    assert {"string", "boolean"} <= types, types
    assert any(b.get("type") == "number" for b in props["energy_level"]["anyOf"])
    # the reference types interrupt_on_noise as boolean or integer; the bundled
    # schema takes the boolean only, so an integer is refused offline
    noise = props["interrupt_on_noise"]["anyOf"]
    assert not any(b.get("type") == "integer" for b in noise), noise
    # a misspelt key is accepted by the schema, so the exact-key check is the guard
    assert "enable_barg" not in props

    node = V.node_surface(HERE, json.dumps([o for o, _ok in VARIANTS]),
                          json.dumps([raw for raw, _ in BARGES]),
                          json.dumps([raw for raw, _ in NUMBERS]),
                          json.dumps(BAD_INTS),
                          env={"SWML_BASIC_AUTH_USER": USER,
                               "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                               "BARGE_MIN_WORDS": "4"})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        check(node["doc"], node["variants"], "typescript")
        check_parses(node["barge"], node["number"], node["badInt"], "typescript")
        ts_note = ("typescript renders the same eleven params, the same six variants "
                   "and the same parses")

    print(f"ok: ai.params carries exactly {sorted(EXPECTED)} with barge_min_words 4; "
          f"the schema bounds them and refuses 100 words and 249 ms while accepting "
          f"99 and 250; ENABLE_BARGE=false parses to the boolean, ENERGY_LEVEL=52.5 "
          f"to a float, and a non-integer setting stops the process; a misspelt key "
          f"validates, so the exact-key check is the guard; {ts_note}")


if __name__ == "__main__":
    main()
