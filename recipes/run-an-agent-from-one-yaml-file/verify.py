"""Prove the claim without a network.

Claim: one SWML document hosted on SignalWire runs a complete agent, with no SDK
and no server.

Proof: the document validates against the SDK's bundled SWML schema, carries a
complete `ai` verb, and contains nothing that requires a service of yours. The
last part is the claim: no SWAIG function, so no callback URL, so nothing to
deploy. The only URL is the post-prompt, which receives a result rather than
serving the agent.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    doc = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(doc)

    names = V.verb_names(doc)
    assert names == ["answer", "ai", "hangup"], names

    ai = V.first(doc, "ai")

    # A complete agent: something to say, and a shape for what it collects.
    assert ai["prompt"]["text"].strip(), ai["prompt"]
    assert ai["post_prompt"]["text"].strip(), ai["post_prompt"]
    assert ai["post_prompt_url"].startswith("https://"), ai

    # No SDK, and no tool of any kind, so nothing here depends on a
        # service of ours answering a tool call. A DataMap tool would also be
    # serverless; this agent simply has none.
    assert "SWAIG" not in ai, (
        "no SWAIG block at all: a handler-backed tool would need the server "
        "this recipe claims not to need"
    )

        # One URL, and it is a sink rather than a source: it receives a
    # report after the call, and nothing is served from it.
    urls = [v for k, v in ai.items() if isinstance(v, str) and v.startswith("http")]
    assert urls == [ai["post_prompt_url"]], urls

    # Bounded, so an abandoned call does not sit open.
    params = ai["params"]
    assert params["inactivity_timeout"] > 0, params
    assert params["attention_timeout"] > 0, params

    # The recogniser is told the words it would otherwise guess at.
    assert any("Ridgeline" in h for h in ai["hints"]), ai["hints"]
    assert ai["languages"][0]["code"] and ai["languages"][0]["voice"], ai["languages"]

    print(f"ok: {' -> '.join(names)}; a complete ai verb with no SWAIG and one "
          f"URL, the post-prompt result sink")


if __name__ == "__main__":
    main()
