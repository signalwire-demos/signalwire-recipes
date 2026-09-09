"""Prove the claim without a network.

Claim: recording starts from the consent tool's result, not before, and no
business step is reachable while consent is still outstanding.

Proof: the rendered SWML shows the disclosure step exposing only the consent
tool, and no record_call anywhere in the document. Note what this cannot
prove: the handler receives the answer the model extracted, so the cases below
exercise the decision on that string, not the caller's audio.
Running the handler shows recording emitted on agreement, withheld on refusal,
and withheld again on an ambiguous answer.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


def actions(result):
    return result.get("action", [])


def recording_in(result):
    """The record_call the platform would run, if any."""
    for a in actions(result):
        main = a.get("SWML", {}).get("sections", {}).get("main", [])
        for verb in main:
            if "record_call" in verb:
                return verb["record_call"]
    return None


def main():
    V.sdk_banner()
    from app import IntakeAgent

    agent = IntakeAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)

    # Nothing in the document records. If it did, recording would start before
    # the caller was ever asked.
    assert "record_call" not in json.dumps(doc), doc

    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    steps = {s["name"]: s for s in ai["prompt"]["contexts"]["default"]["steps"]}

    # While consent is outstanding, the account tool is not on the table.
    # Not a lock: the runtime can still advance, which is why get_balance
    # re-checks the state further down.
    assert steps["disclose"]["functions"] == ["record_consent"], steps
    assert "get_balance" not in steps["disclose"]["functions"], steps
    assert steps["disclose"]["valid_steps"] == [], steps
    assert steps["assist"]["functions"] == ["get_balance"], steps

    # Agreement: recording starts here, from this result.
    r = agent._execute_swaig_function("record_consent", {"answer": "Yes, that's fine."},
                                      call_id="c1")
    rec = recording_in(r)
    assert rec is not None, r
    assert rec["direction"] == "both" and rec["stereo"] is True, rec
    assert {"set_global_data": {"recording": "consented"}} in actions(r), r
    assert {"change_step": "assist"} in actions(r), r

    # Refusal: the call goes on, nothing records.
    r = agent._execute_swaig_function("record_consent", {"answer": "No, please don't."},
                                      call_id="c1")
    assert recording_in(r) is None, r
    assert {"set_global_data": {"recording": "declined"}} in actions(r), r
    assert {"change_step": "assist"} in actions(r), r

    # Ambiguous is not consent: no recording, and no move onward either.
    # The first three are sol's: against substring matching every one of them
    # consented and started recording, because each contains "yes" or "sure".
    NOT_CONSENT = (
        "yesterday",
        "I can't say yes",
        "perhaps, sure",
        "I guess it depends",
        "why do you ask",
        "no idea what you mean by that",
        "",
    )
    for vague in NOT_CONSENT:
        r = agent._execute_swaig_function("record_consent", {"answer": vague},
                                          call_id="c1")
        assert recording_in(r) is None, (vague, r)
        assert not actions(r), (vague, r)
        assert r["response"].startswith("UNCLEAR"), (vague, r)

    # Wording that is a real yes still works, so the strictness has not simply
    # broken the happy path.
    for yes in ("Yes.", "yeah", "That's fine", "Sure, that's fine", "OK"):
        r = agent._execute_swaig_function("record_consent", {"answer": yes},
                                          call_id="c1")
        assert recording_in(r) is not None, (yes, r)

    for no in ("No.", "No thanks", "I'd rather not", "Please don't"):
        r = agent._execute_swaig_function("record_consent", {"answer": no},
                                          call_id="c1")
        assert recording_in(r) is None, (no, r)
        assert {"set_global_data": {"recording": "declined"}} in actions(r), (no, r)

    # A step is not a boundary: the account tool refuses on its own state,
    # however the call arrived at the step that exposes it.
    r = agent._execute_swaig_function("get_balance", {}, call_id="c1",
                                      raw_data={"global_data": {}})
    assert r["response"].startswith("NOT_DISCLOSED"), r
    for answered in ("consented", "declined"):
        r = agent._execute_swaig_function(
            "get_balance", {}, call_id="c1",
            raw_data={"global_data": {"recording": answered}})
        assert "balance" in r["response"], (answered, r)

    print(f"ok: no record_call in the document; consent emits "
          f"record_call(stereo, both) + change_step; {len(NOT_CONSENT)} "
          f"non-answers record nothing; get_balance refuses undisclosed")


if __name__ == "__main__":
    main()
