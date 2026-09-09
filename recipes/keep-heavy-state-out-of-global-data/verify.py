"""Prove the claim without a network.

Claim: per-call state lives server-side keyed by call_id, and only a short
AI-facing summary is written to global_data.

Proof: record three long findings on one call and one on another. After each,
the whole `action` list is measured and stays under a fixed size, and the
`set_global_data` it carries is exactly a count and the distinct areas. The
store holds the full text under each call id, the two calls do not mix, and a
snapshot of the store is unchanged by another call's write and by an invalid
one. Twenty more findings on one area leave the action bounded.
`read_back_report` returns every detail from the store for its own call and
nothing for a call with no findings. Expected values live here, not in app.py.
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

# Expected values live here, not imported from app.py.
AREAS = ["brakes", "gears", "wheels", "frame", "lights"]
FINDINGS_A = [
    ("brakes", "Front pads worn to the wear line, rear pads glazed, both calipers "
               "sticking on release; recommend new pads and a caliper service."),
    ("gears", "Rear derailleur hanger bent inwards, cable frayed at the barrel "
              "adjuster, shifting skips under load in the three smallest cogs."),
    ("wheels", "Rear wheel out of true by about four millimetres with two loose "
               "spokes on the drive side; front bearing has slight play."),
]
FINDING_B = ("lights", "Rear light bracket cracked.")
ACTION_CAP = 120  # bytes of JSON for the whole action list of one tool result


def run(agent, call_id, tool, **args):
    raw = {"call_id": call_id, "argument": {"parsed": [args]}}
    return agent._execute_swaig_function(tool, args, call_id=call_id, raw_data=raw)


def main():
    V.sdk_banner()
    import app as recipe

    agent = recipe.agent
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fns = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert sorted(fns) == ["read_back_report", "record_finding"], sorted(fns)
    assert fns["record_finding"]["parameters"]["properties"]["area"]["enum"] == AREAS

    recipe.STORE.clear()
    for n, (area, detail) in enumerate(FINDINGS_A, 1):
        r = run(agent, "call-A", "record_finding", area=area, detail=detail)
        # the whole wire action, measured first and on its own
        wire = json.dumps(r["action"])
        assert len(wire) <= ACTION_CAP, (len(wire), wire)
        assert detail[:20] not in wire, wire
        # then exactly what it carries, and what the model is told
        assert r["action"] == [{"set_global_data": {
            "findings": n, "areas": ", ".join(a for a, _ in FINDINGS_A[:n])}}], r
        assert r["response"] == f"Recorded {area}. {n} findings so far.", r
    # the store has every word, and it is already bigger than the cap allows
    stored = recipe.STORE["call-A"]
    assert [(f["area"], f["detail"]) for f in stored] == FINDINGS_A, stored
    assert len(json.dumps(stored)) > ACTION_CAP * 3, len(json.dumps(stored))
    snapshot = json.dumps(recipe.STORE, sort_keys=True)

    # another call is another record, and call-A's is untouched
    r = run(agent, "call-B", "record_finding", area=FINDING_B[0], detail=FINDING_B[1])
    assert r["action"] == [{"set_global_data": {"findings": 1, "areas": "lights"}}], r
    assert [(f["area"], f["detail"]) for f in recipe.STORE["call-B"]] == [FINDING_B]
    assert json.dumps({"call-A": recipe.STORE["call-A"]}, sort_keys=True) == \
        json.dumps({"call-A": json.loads(snapshot)["call-A"]}, sort_keys=True)

    # the summary is bounded by the areas, not by the number of findings
    for i in range(20):
        r = run(agent, "call-B", "record_finding", area="lights",
                detail=f"Further note {i}: " + "x" * 80)
    assert len(json.dumps(r["action"])) <= ACTION_CAP, r["action"]
    assert r["action"][0]["set_global_data"] == {"findings": 21, "areas": "lights"}
    assert len(recipe.STORE["call-B"]) == 21

    # the read-back comes from the store, in full, for its own call only
    r = run(agent, "call-A", "read_back_report")
    assert "action" not in r, r
    for _, detail in FINDINGS_A:
        assert detail in r["response"], (detail[:30], r["response"][:80])
    assert FINDING_B[1] not in r["response"]
    r = run(agent, "call-C", "read_back_report")
    assert r["response"].startswith("INCOMPLETE") and "action" not in r, r

    # a bad finding writes nowhere: the store is byte-for-byte what it was
    before = json.dumps(recipe.STORE, sort_keys=True)
    r = run(agent, "call-A", "record_finding", area="saddle", detail="torn")
    assert r["response"].startswith("INVALID") and "action" not in r, r
    assert json.dumps(recipe.STORE, sort_keys=True) == before

    print(f"ok: three findings on call-A kept every action under {ACTION_CAP} "
          f"bytes while the store holds {len(json.dumps(stored))} bytes; 21 "
          f"findings on call-B stay bounded; calls do not mix; read_back_report "
          f"returns the full text from the store")


if __name__ == "__main__":
    main()
