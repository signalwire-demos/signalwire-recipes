"""Prove the claim without a network.

Claim: when the call ends, the post-prompt returns typed JSON about the
conversation to your webhook, and the payload is yours to route.

Proof: the rendered SWML carries the post-prompt text and a post_prompt_url, so
the platform knows what to ask for and where to send it. Driving the summary
handler the way the platform does shows the record filed on a good payload, and
quarantined rather than trusted on a bad one.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


def main():
    V.sdk_banner()
    import app as recipe

    agent = recipe.SupportAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]

    # The platform is told what to produce and where to send it.
    assert ai["post_prompt"], ai
    text = json.dumps(ai["post_prompt"])
    for key in ("outcome", "reason", "callback_number"):
        assert key in text, (key, text)
    assert ai["post_prompt_url"], ai

    # A good payload, delivered the way the platform delivers it.
    good = {"outcome": "callback_requested",
            "reason": "Wheel true needed, no slots today.",
            "callback_number": "+15550100077"}
    agent.on_summary(good, {"call_id": "c1"})
    assert recipe.filed == [{"call_id": "c1", **good}], recipe.filed
    assert recipe.quarantine == [], recipe.quarantine

    # The model wrote the JSON, so the handler does not have to believe it.
    bad = [
        ({"outcome": "solved", "reason": "x", "callback_number": None},
         "outcome"),
        ({"outcome": "callback_requested", "reason": "x",
          "callback_number": None}, "no callback_number"),
        ({"outcome": "resolved", "reason": "x",
          "callback_number": "555 0100"}, "E.164"),
        ({"outcome": "resolved"}, "missing"),
        ("the caller was happy", "not an object"),
        # sol: "+" and "+abc" passed the old startswith("+") check
        ({"outcome": "resolved", "reason": "x", "callback_number": "+"},
         "E.164"),
        ({"outcome": "resolved", "reason": "x", "callback_number": "+abc"},
         "E.164"),
        ({"outcome": "resolved", "reason": "x",
          "callback_number": "+1234567890123456"}, "E.164"),
        # an empty reason is a row nobody can act on
        ({"outcome": "resolved", "reason": "   ", "callback_number": None},
         "reason is empty"),
        # the post-prompt asked for exactly three keys
        ({"outcome": "resolved", "reason": "x", "callback_number": None,
          "sentiment": "positive"}, "unexpected sentiment"),
    ]
    for payload, expected in bad:
        agent.on_summary(payload, {"call_id": "c2"})
    assert len(recipe.filed) == 1, recipe.filed          # nothing else filed
    assert len(recipe.quarantine) == len(bad), recipe.quarantine
    for (payload, expected), held in zip(bad, recipe.quarantine):
        assert expected in held["why"], (expected, held)

    # The platform's other delivery shape: JSON as a raw string.
    import logging
    quiet = logging.getLogger("verify")
    assert agent._find_summary_in_post_data(
        {"post_prompt_data": {"raw": json.dumps(good)}}, quiet
    ) == good
    assert agent._find_summary_in_post_data(
        {"post_prompt_data": {"parsed": [good]}}, quiet
    ) == good

    print(f"ok: post_prompt names {len(recipe.REQUIRED)} keys and a "
          f"post_prompt_url; 1 record filed, {len(recipe.quarantine)} "
          f"quarantined with reasons")


if __name__ == "__main__":
    main()
