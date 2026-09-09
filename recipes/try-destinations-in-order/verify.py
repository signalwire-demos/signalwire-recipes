"""Prove the claim without a network.

Claim: one `connect` carries a `serial` or a `parallel` list of destinations,
and `result` carries the branch that runs when `connect_result` is "failed".

Proof: both surfaces validate against the SWML schema. The serial connect
carries the three destinations in the configured order with a timeout, and
`result.case` has a "connected" and a "failed" branch that each end the call.
The parallel section carries the phone destinations and a "failed" branch.
The Python surface renders a document equal to the YAML one. Then the shape
rule: a connect with both `to` and `serial` fails schema validation, because
the schema is a oneOf over single, serial, parallel and serial_parallel.
Expected values live here, not in app.py.
"""
import copy
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# Expected values live here, not imported from app.py.
ORDER = ["+15550100001", "sip:workshop@pbx.example.com", "+15550100003"]
PARALLEL = ["+15550100001", "+15550100003"]
os.environ["DESTINATIONS"] = ",".join(ORDER)
os.environ["RING_SECONDS"] = "15"


def check(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "play", "connect"], (label, V.verb_names(doc))
    c = V.first(doc, "connect")
    assert "to" not in c, (label, "a serial connect has no single to")
    assert [d["to"] for d in c["serial"]] == ORDER, (label, c["serial"])
    assert c["timeout"] == 15, (label, c)
    cases = c["result"]["case"]
    assert set(cases) == {"connected", "failed"}, (label, cases)
    for branch in cases.values():
        assert [list(v)[0] for v in branch] == ["play", "hangup"], (label, branch)
    assert "Nobody" in cases["failed"][0]["play"]["url"], (label, cases["failed"])

    p = V.first(doc, "connect", "parallel")
    assert [d["to"] for d in p["parallel"]] == PARALLEL, (label, p)
    assert list(p["result"]["case"]) == ["failed"], (label, p["result"])


def main():
    V.sdk_banner()
    import app as recipe
    py = recipe.build().get_document()
    check(py, "python")
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    check(y, "yaml")
    # the two surfaces are the same document, not two documents that share
    # the checked fields
    assert py == y, "python and yaml surfaces differ"

    # one shape at a time: a connect cannot carry both a single `to` and a list
    bad = copy.deepcopy(y)
    V.first(bad, "connect")["to"] = "+15550100009"
    try:
        V.validate_swml(bad)
    except Exception as e:
        assert "connect" in str(e).lower() or "oneOf" in str(e) or "schema" in str(e).lower(), e
    else:
        raise AssertionError("a connect with both to and serial validated")

    print(f"ok: connect carries serial {ORDER} with a 15s timeout and result "
          f"branches for connected and failed that end the call; the parallel "
          f"section carries {PARALLEL}; both surfaces render the same document; "
          f"to plus serial is refused by the schema")


if __name__ == "__main__":
    main()
