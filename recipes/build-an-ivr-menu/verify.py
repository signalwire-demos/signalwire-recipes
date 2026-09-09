"""Prove the claim without a network.

Claim: press-1 menus branch to different sections without a line of server code.

Proof: the YAML surface and the Python-built document both validate against the
SDK's bundled SWML schema; the prompt collects exactly one digit; every switch
case transfers to a section that exists; the fall-through re-prompts.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402


def check(doc, label):
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names == ["answer", "prompt", "switch"], (label, names)
    prompt = V.first(doc, "prompt")
    assert prompt["max_digits"] == 1, (label, prompt)
    assert str(prompt["play"]).startswith("say:"), (label, prompt)
    switch = V.first(doc, "switch")
    assert switch["variable"] == "prompt_value", (label, switch)
    sections = set(doc["sections"])
    for digit, steps in switch["case"].items():
        (verb,) = steps
        dest = verb["transfer"]["dest"]
        assert dest in sections, (label, digit, dest, sections)
        assert dest != "main", (label, digit)
    assert set(switch["case"]) == {"1", "2", "3"}, (label, switch["case"])
    default_names = [next(iter(v)) for v in switch["default"]]
    assert default_names == ["play", "transfer"], (label, default_names)
    assert switch["default"][1]["transfer"]["dest"] == "main", label
    for s in ("sales", "support"):
        assert "connect" in V.verb_names(doc, s), (label, s)
    assert "connect" not in V.verb_names(doc, "hours"), label
    return sections


def main():
    V.sdk_banner()
    from app import build
    py_doc = build().get_document()
    yaml_doc = V.load_yaml(HERE / "swml" / "agent.yaml")
    a, b = check(py_doc, "python"), check(yaml_doc, "yaml")
    assert a == b, (a, b)
    print(f"ok: 3 cases -> {sorted(a - {'main'})}; default re-prompts; both surfaces validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
