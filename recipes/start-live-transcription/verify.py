"""Prove the claim without a network.

Claim: partial and final transcripts of both legs arrive at your webhook while
the call is in progress, and a summary when it ends.

Proof: both surfaces validate against the SWML schema; live_transcribe starts
before connect with live_events and ai_summary on, both directions, and the
webhook URL; the webhook handler keeps finals per call, keeps the summary, and
drops partials.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("PUBLIC_URL", "https://recipes.example.test")

import verifylib as V  # noqa: E402


def check(doc, label):
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names.index("live_transcribe") < names.index("connect"), (label, names)
    start = V.first(doc, "live_transcribe")["action"]["start"]
    assert start["live_events"] is True and start["ai_summary"] is True, (label, start)
    assert set(start["direction"]) == {"remote-caller", "local-caller"}, (label, start)
    assert start["lang"] and start["webhook"].endswith("/transcript"), (label, start)
    return start


def main():
    V.sdk_banner()
    import app as recipe
    s = check(recipe.build().get_document(), "python")
    assert s["webhook"] == "https://recipes.example.test/transcript", s
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    c = recipe.app.test_client()
    post = lambda **e: c.post("/transcript", json=e)  # noqa: E731
    post(call_id="c1", type="partial", text="hello my na", direction="remote-caller")
    assert recipe.transcripts == {}, recipe.transcripts
    post(call_id="c1", type="final", text="Hello, my name is Dana.", direction="remote-caller")
    post(call_id="c1", type="final", text="Hi Dana, how can I help?", direction="local-caller")
    assert [t["who"] for t in recipe.transcripts["c1"]] == ["remote-caller", "local-caller"]
    post(call_id="c1", type="summary", summary="Dana asked about a charge.")
    assert recipe.summaries["c1"] == "Dana asked about a charge."
    print("ok: live_transcribe(start: live_events, ai_summary, both legs) before connect; finals kept, partials dropped, summary kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
