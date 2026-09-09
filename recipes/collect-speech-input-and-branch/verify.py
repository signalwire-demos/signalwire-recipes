"""Prove the claim without a network.

Claim: the caller says what they want and the document branches on the
recognised phrase, with no AI agent involved.

Proof: both surfaces validate against the SWML schema. The prompt sets speech
parameters and no digit parameters, which is what turns speech detection on and
leaves the keypad off. The switch reads `prompt_value`, the collected utterance,
rather than `prompt_result`, which is the status of the attempt. Every case
targets a section that exists, and no `ai` verb appears anywhere.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# from the prompt schema: "Speech detection is not enabled unless at least one
# speech parameter is set. If only speech parameters are set (and no digit
# parameters), digit detection is not enabled."
SPEECH = {"speech_timeout", "speech_end_timeout", "speech_language",
          "speech_hints", "speech_engine"}
DIGIT = {"max_digits", "terminators", "digit_timeout"}


def check(doc, label):
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names[:3] == ["answer", "prompt", "switch"], (label, names)

    # No AI anywhere: a recogniser and a switch, not an agent. Checked as a
    # verb name per section, because "ai" is a substring of "main".
    for section, verbs in doc["sections"].items():
        for verb in verbs:
            assert "ai" not in verb, (label, section, verb)

    prompt = V.first(doc, "prompt")
    assert prompt["play"], (label, prompt)
    # speech on, keypad off
    assert SPEECH & set(prompt), (label, sorted(prompt))
    assert not DIGIT & set(prompt), (label, sorted(DIGIT & set(prompt)))
    assert prompt["speech_hints"], (label, prompt)

    sw = V.first(doc, "switch")
    # prompt_value is what they said; prompt_result is whether it worked
    assert sw["variable"] == "prompt_value", (label, sw)

    # Every branch lands somewhere real, including the retry.
    sections = set(doc["sections"])
    for phrase, verbs in sw["case"].items():
        dest = verbs[0]["transfer"]["dest"]
        assert dest in sections, (label, phrase, dest, sorted(sections))
    assert sw["default"], (label, sw)
    assert sw["default"][-1]["transfer"]["dest"] in sections, (label, sw)

        # Each hint the recogniser is given is a phrase the switch can act on.
    assert set(prompt["speech_hints"]) <= set(sw["case"]), (
        label, sorted(set(prompt["speech_hints"]) - set(sw["case"])))

    # Two phrases reach billing, and three destinations remain. The README
    # claims this of both surfaces, so both surfaces are checked.
    assert sw["case"]["account"] == sw["case"]["billing"] == [
        {"transfer": {"dest": "billing"}}
    ], (label, sw["case"])
    dests = {v[0]["transfer"]["dest"] for v in sw["case"].values()}
    assert len(dests) == 3, (label, sorted(dests))
    return sw


def main():
    V.sdk_banner()
    import app as recipe

    sw = check(recipe.build().get_document(), "python")
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    print(f"ok: prompt listens on {sorted(SPEECH & set(V.first(recipe.build().get_document(), 'prompt')))} "
          f"with no digit parameters; switch on prompt_value covers "
          f"{sorted(sw['case'])} plus a default")


if __name__ == "__main__":
    main()
