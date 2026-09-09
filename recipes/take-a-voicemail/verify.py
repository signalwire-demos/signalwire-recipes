"""Prove the claim without a network.

Claim: when the bridge to the owner does not happen, the document plays a
prompt and records the caller's message in the foreground. The recording
events go to `status_url`.

Proof: both surfaces validate against the SWML schema. The `connect` carries
the owner's number and a timeout. Its `result.case.failed` branch is play,
record, play, hangup, with the exact prompt and thanks. The record carries a
beep, an mp3 format, a max length, an end-of-silence timeout, `#` as the
terminator and a `status_url` on your host. The connected branch only hangs
up. The two surfaces render the same document. Expected values live here, not
in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# Expected values live here, not imported from app.py.
OWNER = "+15550100001"
os.environ["OWNER_NUMBER"] = OWNER
os.environ["RING_SECONDS"] = "20"
os.environ["PUBLIC_URL"] = "https://your-host.example.com"
PROMPT = "say:Leave a message after the tone."
THANKS = "say:Thanks. We will call you back."
RECORD = {"beep": True, "format": "mp3", "max_length": 120,
          "end_silence_timeout": 5, "terminators": "#",
          "status_url": "https://your-host.example.com/recording-status"}


def check(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "connect"], (label, V.verb_names(doc))
    c = V.first(doc, "connect")
    assert c["to"] == OWNER and c["timeout"] == 20, (label, c)
    cases = c["result"]["case"]
    assert set(cases) == {"connected", "failed"}, (label, cases)
    assert [list(v)[0] for v in cases["connected"]] == ["hangup"], (label, cases)
    failed = cases["failed"]
    assert [list(v)[0] for v in failed] == ["play", "record", "play", "hangup"], (label, failed)
    assert failed[0]["play"]["url"] == PROMPT, (label, failed[0])
    assert failed[1]["record"] == RECORD, (label, failed[1])
    assert failed[2]["play"]["url"] == THANKS, (label, failed[2])


def main():
    V.sdk_banner()
    import app as recipe
    py = recipe.build().get_document()
    check(py, "python")
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    check(y, "yaml")
    assert py == y, "python and yaml surfaces differ"

    print(f"ok: connect {OWNER} for 20s; the failed branch plays a prompt, records "
          f"an mp3 up to 120s with a beep and # to stop, posting events to "
          f"{RECORD['status_url']}, then thanks and hangs up; both surfaces equal")


if __name__ == "__main__":
    main()
