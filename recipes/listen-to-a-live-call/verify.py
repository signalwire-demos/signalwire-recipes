"""Prove the claim without a network.

Claim: call audio is forked to your WebSocket while the call continues, and the
participants hear nothing.

Proof: the document validates against the SWML schema, taps before `connect` so
the bridged leg is inside the tap, sends both directions to a socket URI, and
carries a control_id so it can be stopped. Nothing in the document plays,
announces or joins anything, which is what "the participants hear nothing"
means in an artifact.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("PUBLIC_URL", "https://recipes.example.test")
os.environ.setdefault("AUDIO_WS", "wss://recipes.example.test/ws/audio")

import verifylib as V  # noqa: E402

# the schema's own list
SCHEMES = ("ws://", "wss://", "rtp://")
CODECS = ("PCMU", "PCMA")


def main():
    V.sdk_banner()
    import app as recipe

    doc = recipe.build().get_document()
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names == ["answer", "tap", "connect", "hangup"], names

    # After connect the tap would not run until the bridge had ended.
    assert names.index("tap") < names.index("connect"), names

    tap = V.first(doc, "tap")

    # uri is the only required field, and it decides the transport.
    assert tap["uri"].startswith(SCHEMES), tap
    assert tap["uri"].startswith(("ws://", "wss://")), tap   # the claim says WebSocket
    assert tap["codec"] in CODECS, tap

    # The conversation, not one side of it.
    assert tap["direction"] == "both", tap

    # A tap you cannot stop is a tap you cannot turn off.
    assert tap["control_id"], tap
    assert tap["status_url"].endswith("/tap-status"), tap

    # "the participants hear nothing": nothing in the document makes sound
    # or adds anybody to the call.
    for verb in ("play", "prompt", "join_conference", "say"):
        assert verb not in names, (verb, names)

    # The status webhook keeps the last state per tap, keyed by control_id.
    client = recipe.app.test_client()
    client.post("/tap-status", json={"control_id": tap["control_id"],
                                     "state": "tapping"})
    assert recipe.taps[tap["control_id"]] == "tapping", recipe.taps

    print(f"ok: tap({tap['direction']}, {tap['codec']}) to {tap['uri']} before "
          f"connect, control_id={tap['control_id']!r}; nothing in the document "
          f"is audible to the call")


if __name__ == "__main__":
    main()
