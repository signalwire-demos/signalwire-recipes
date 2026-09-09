"""Prove the claim without a network.

Claim: the agent answers in the caller's language and switches mid-conversation
without a transfer.

Proof: the rendered SWML carries every language with its own voice and code,
`languages_enabled` is on (without it the list is ignored), and the document
contains no transfer or connect, so the switch happens inside one AI session
rather than by routing the call somewhere else.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


# The claim names three languages, so the verifier names them too. Importing
# LANGUAGES from the implementation would compare the recipe with itself, and
# swapping both surfaces to unrelated languages would still pass.
EXPECTED = [
    ("English", "en-US", "rime.spore"),
    ("Spanish", "es-ES", "rime.marisol"),
    ("French", "fr-FR", "rime.celeste"),
]

# what the prompt has to actually instruct, not merely mention
DIRECTIVES = ("whatever language the caller is speaking",
              "change with them",
              "do not comment on it")


def check(doc, label):
    """Everything the claim needs, run against both surfaces alike."""
    V.validate_swml(doc)

    # Exactly one AI session. Taking the first `ai` verb would let a document
    # with two of them pass a claim about staying inside one.
    ais = [v["ai"] for v in doc["sections"]["main"] if "ai" in v]
    assert len(ais) == 1, (label, len(ais))
    ai = ais[0]

    # the switch, without which the list is ignored
    assert ai["params"]["languages_enabled"] is True, (label, ai["params"])

    # The exact languages the claim advertises, in order, with their voices.
    got = [(l["name"], l["code"], l["voice"]) for l in ai["languages"]]
    assert got == EXPECTED, (label, got)

    # A voice per language, not one voice reading three.
    voices = [v for _, _, v in got]
    assert len(set(voices)) == len(voices), (label, voices)

    # "without a transfer": the call never leaves this agent
    names = V.verb_names(doc)
    for verb in ("transfer", "connect"):
        assert verb not in names, (label, verb, names)

    # The prompt must instruct the behaviour, not merely mention the word:
    # "language" alone passes for a prompt that says the opposite.
    prompt = json.dumps(ai["prompt"]).lower()
    for directive in DIRECTIVES:
        assert directive in prompt, (label, directive)
    return ai


def main():
    V.sdk_banner()
    from app import FrontDeskAgent

    agent = FrontDeskAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    ai = check(doc, "python")

    langs = ai["languages"]
    assert len(langs) == len(EXPECTED), langs

    assert "SWAIG" not in ai or not ai["SWAIG"].get("functions"), ai.get("SWAIG")

    # The hand-written surface is checked against the same expected list, so
    # the two surfaces are compared with a third thing rather than each other.
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    print(f"ok: languages_enabled with {[l['code'] for l in langs]}, "
          f"a distinct voice each, and no transfer or connect in the document")


if __name__ == "__main__":
    main()
