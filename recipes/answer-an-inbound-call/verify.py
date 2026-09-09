"""Prove the claim without a network.

Claim: a number rings your URL, your response answers it, plays TTS and hangs up.

Proof: both surfaces validate against the SDK's bundled SWML schema, and the
three verbs appear in order: answer, so the call is up explicitly rather than by
play's auto_answer, then play, then hangup.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("GREETING", "Thanks for calling Ridgeline Cycles.")

import verifylib as V  # noqa: E402


def check(doc, label):
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names == ["answer", "play", "hangup"], (label, names)

    # answer first, so the call is up before the greeting rather than relying
    # on play's auto_answer to do it implicitly.
    assert names.index("answer") < names.index("play"), (label, names)

    # A bound on a call nobody hung up. 14400 is the documented default, not
    # a documented ceiling, so this only asserts it was set to something.
    answer = V.first(doc, "answer")
    assert isinstance(answer.get("max_duration"), int), (label, answer)
    assert answer["max_duration"] > 0, (label, answer)

    # "say:" is speech; anything else is a file to fetch.
    play = V.first(doc, "play")
    url = play if isinstance(play, str) else play.get("url")
    assert url.startswith("say:"), (label, play)
    assert len(url) > len("say:"), (label, play)
    return url


def main():
    V.sdk_banner()
    import app as recipe

    said = check(recipe.build().get_document(), "python")
    assert said == f"say:{recipe.GREETING}", said

    yaml_said = check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    # SignalWire POSTs to the SWML URL, so that is what has to work.
    client = recipe.app.test_client()
    body = client.post("/greeting").get_json()
    assert V.verb_names(body) == ["answer", "play", "hangup"], body

    print(f"ok: answer(max_duration={V.first(body, 'answer')['max_duration']}) "
          f"-> play -> hangup on both surfaces; served at /greeting")


if __name__ == "__main__":
    main()
