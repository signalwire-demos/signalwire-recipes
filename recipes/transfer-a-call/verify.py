"""Prove the claim without a network.

Claim: a live call is bridged to a number, SIP URI or Resource address, and
optionally returns when the far end hangs up.

Proof: both surfaces validate against the SWML schema; connect names a `to`
and is followed by verbs (the return path); with PERMANENT=true the connect
carries transfer_after_bridge; the SIP variant sets custom INVITE headers.
"""
import importlib
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402


def check(doc, label):
    V.validate_swml(doc)
    names = V.verb_names(doc)
    i = names.index("connect")
    assert names[i + 1:] == ["play", "hangup"], (label, names)  # return path exists
    c = V.first(doc, "connect")
    assert c["to"].startswith("+"), (label, c)
    sip = V.first(doc, "connect", "sip")
    assert sip["to"].startswith("sip:"), (label, sip)
    assert {h["name"] for h in sip["headers"]} == {"X-Account-Id", "X-Source"}, (label, sip)
    return c


def main():
    V.sdk_banner()
    import app as recipe
    c = check(recipe.build().get_document(), "python")
    assert "transfer_after_bridge" not in c, c
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    os.environ["PERMANENT"] = "true"
    recipe = importlib.reload(recipe)
    c = V.first(recipe.build().get_document(), "connect")
    assert c["transfer_after_bridge"] == "true", c
    print("ok: connect -> return path; PERMANENT=true sets transfer_after_bridge; SIP variant carries headers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
