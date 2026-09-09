"""Prove the claim without a network.

Claim: a third party enters a live conference with full audio, and leaving does
not end the call.

Proof: the handler emits a join_conference that is unmuted and carries no coach
target. That is what makes it audible to everyone rather than aimed at one leg.
It neither starts nor ends the room, so the visitor's arrival and departure
leave the call where it was. A room outside the allowed set is
refused, because barging is audible to the customer.
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


def conference_in(result):
    for action in result.get("action", []):
        for verb in action.get("SWML", {}).get("sections", {}).get("main", []):
            if "join_conference" in verb:
                return verb["join_conference"]
    return None


def main():
    V.sdk_banner()
    from app import ALLOWED, SUPERVISORS, BargeAgent

    agent = BargeAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    assert "join_conference" not in json.dumps(doc), doc

    # A caller who is not a supervisor never reaches the room list.
    # A denied room, so the refusal proves the caller was checked first: if
    # the room were considered first this would come back NOT_ALLOWED.
    for stranger in ("+15559999999", ""):
        r = agent._execute_swaig_function(
            "barge_in", {"room": "boardroom"}, call_id="sup-1",
            raw_data={"global_data": {"caller_id_num": stranger}})
        assert conference_in(r) is None, (stranger, r)
        assert r["response"].startswith("NOT_AUTHORISED"), (stranger, r)

    SUP = sorted(SUPERVISORS)[0]

    # Either location authorises: which one the platform populates is not
    # settled by any source we hold, so the check reads both.
    for raw in ({"global_data": {"caller_id_num": SUP}}, {"caller_id_num": SUP}):
        assert conference_in(agent._execute_swaig_function(
            "barge_in", {"room": "support-floor"}, call_id="sup-1",
            raw_data=raw)) is not None, raw
    r = agent._execute_swaig_function("barge_in", {"room": "Support-Floor"},
                                      call_id="sup-1",
                                      raw_data={"global_data": {"caller_id_num": SUP}})
    jc = conference_in(r)
    assert jc is not None, r
    assert jc["name"] == "support-floor", jc

    # Full audio: heard by everyone, aimed at nobody in particular. Either a
    # coach target or muting would make this something other than barging.
    assert jc.get("muted", False) is False, jc
    assert "coach" not in jc, jc

    # A visitor. end_on_exit defaults to False and the SDK omits defaults, so
    # its absence is the claim; start_on_enter defaults True and must be set.
    assert "end_on_exit" not in jc, jc
    assert jc["start_on_enter"] is False, jc

    # Arrival is announced, because the customer hears a new voice.
    assert jc["beep"] == "onEnter", jc

    # Every allowed floor works, and nothing else does.
    for room in ALLOWED:
        got = conference_in(agent._execute_swaig_function(
            "barge_in", {"room": room}, call_id="sup-1",
            raw_data={"global_data": {"caller_id_num": SUP}}))
        assert got["name"] == room, (room, got)
    for denied in ("boardroom", "", "support floor"):
        r = agent._execute_swaig_function("barge_in", {"room": denied},
                                          call_id="sup-1",
                                          raw_data={"global_data": {"caller_id_num": SUP}})
        assert conference_in(r) is None, (denied, r)
        assert r["response"].startswith("NOT_ALLOWED"), (denied, r)

    print(f"ok: unmuted join of {sorted(ALLOWED)} with no coach target, "
          f"beep on enter, neither starting nor ending the room; anything "
          f"outside the list is refused")


if __name__ == "__main__":
    main()
