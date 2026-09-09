"""Prove the claim without a network.

Claim: the whole call is recorded in the background and the recording URL is
delivered to a status URL.

Proof: both surfaces validate against the SWML schema; record_call precedes
connect (so the bridged leg is inside the recording), records both directions,
and names a status_url; the status webhook stores the URL only for a finished
recording.
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
    assert names.index("record_call") < names.index("connect"), (label, names)
    rc = V.first(doc, "record_call")
    assert rc["direction"] == "both" and rc["stereo"] is True, (label, rc)
    assert rc["status_url"].endswith("/recording-status"), (label, rc)
    assert "hangup" in names, (label, names)
    return rc["status_url"]


def main():
    V.sdk_banner()
    import app as recipe
    url = check(recipe.build().get_document(), "python")
    assert url == "https://recipes.example.test/recording-status", url
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    c = recipe.app.test_client()
    body = c.get("/record").get_json()
    assert V.verb_names(body)[1] == "record_call", body

    c.post("/recording-status", json={"call_id": "c1", "state": "recording"})
    assert recipe.recordings == {}, recipe.recordings
    c.post("/recording-status", json={"call_id": "c1", "state": "finished",
                                      "url": "https://example.test/rec.wav", "duration": 42})
    assert recipe.recordings["c1"]["url"] == "https://example.test/rec.wav", recipe.recordings
    print("ok: record_call(both, stereo) before connect; URL captured on state=finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
