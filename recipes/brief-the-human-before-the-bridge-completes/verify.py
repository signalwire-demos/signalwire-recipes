"""Prove the claim without a network.

Claim: the receiving agent hears a whispered summary before the caller's audio
is joined.

Proof: the handler emits a connect whose `confirm` carries the briefing inline.
`confirm` runs on the answering leg before the two legs are joined, so what it
plays reaches the agent and not the caller. The briefing is built from
collected state, carries only the fields chosen in code, and a transfer with
nothing collected is refused rather than sent with an empty summary.
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

STATE = {
    "caller_name": "Dana Whitfield",
    "reason": "a refund on order 48815",
    "account_status": "in good standing",
    # never briefed: chosen in code, not by the model
    "card_last_four": "6411",
    "internal_note": "threatened to churn in March",
}


def connect_in(result):
    for action in result.get("action", []):
        for verb in action.get("SWML", {}).get("sections", {}).get("main", []):
            if "connect" in verb:
                return verb["connect"]
    return None


def main():
    V.sdk_banner()
    from app import BRIEFED, HUMAN, IntakeAgent, briefing_from

    agent = IntakeAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    # nothing connects from the document; only the handler does
    assert "connect" not in V.verb_names(doc), V.verb_names(doc)

    r = agent._execute_swaig_function("transfer_to_human", {}, call_id="c1",
                                      raw_data={"global_data": STATE})
    conn = connect_in(r)
    assert conn is not None, r
    assert conn["to"] == HUMAN, conn

    # The briefing rides in confirm, which runs on the answering leg before
    # the bridge completes. Anything played in `main` instead would be heard
    # by the caller.
    assert "confirm" in conn, conn
    (spoken,) = conn["confirm"]
    said = spoken["play"]["url"]
    assert said.startswith("say:"), said
    assert conn["confirm_timeout"] > 0, conn

    # The whole SWML the platform receives is the connect: nothing plays to
    # the caller alongside it.
    (action,) = r["action"]
    assert action["SWML"]["sections"]["main"] == [{"connect": conn}], action

    # What the agent is told: the collected fields, and only those.
    for key in ("Dana Whitfield", "a refund on order 48815", "in good standing"):
        assert key in said, (key, said)
    # Whole fields are excluded. Nothing is redacted inside an allowed one,
    # which the README says plainly rather than implying otherwise.
    for excluded in (STATE["card_last_four"], STATE["internal_note"]):
        assert excluded not in said, (excluded, said)
    assert set(BRIEFED) == {"caller_name", "reason", "account_status"}, BRIEFED

    # A missing field degrades the sentence rather than breaking it.
    partial = briefing_from({"caller_name": "Dana"})
    assert "Dana" in partial and "unstated reason" in partial, partial

    # Nothing collected means no transfer: an empty briefing is worse than
    # none, because the agent answers expecting context.
    for missing in ({}, {"caller_name": "Dana"}, {"reason": "a refund"}):
        r = agent._execute_swaig_function("transfer_to_human", {}, call_id="c1",
                                          raw_data={"global_data": missing})
        assert connect_in(r) is None, (missing, r)
        assert r["response"].startswith("NOT_READY"), (missing, r)

    print(f"ok: connect to {HUMAN} with the briefing inside confirm "
          f"(timeout {conn['confirm_timeout']}s); only {sorted(BRIEFED)} are "
          f"spoken, and an incomplete intake does not transfer")


if __name__ == "__main__":
    main()
