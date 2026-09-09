"""Prove the claim without a network.

Claim: a supervisor joins the conference as a coach, heard by one agent and
silent to everyone else.

Proof: the handler emits a join_conference aimed at a specific call id, which is
what makes it coaching rather than attendance. The supervisor joins muted, with
no beep, and cannot start or end the room. Coaching an agent who is not on a
call is refused, because that would join the supervisor as an ordinary
participant the customer can hear.
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

ROOM = "support-floor"


def conference_in(result):
    """The join_conference the platform would run, if any."""
    for action in result.get("action", []):
        for verb in action.get("SWML", {}).get("sections", {}).get("main", []):
            if "join_conference" in verb:
                return verb["join_conference"]
    return None


def main():
    V.sdk_banner()
    from app import ON_CALL, SUPERVISORS, SupervisorAgent

    agent = SupervisorAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)

    # Nothing joins a conference from the document itself.
    assert "join_conference" not in json.dumps(doc), doc

    # A caller who is not a supervisor gets nowhere, whatever they ask for.
    # Refusal has to happen before the agent is looked up, not after. With
    # ON_CALL replaced by something that raises on use, an unauthorised
    # caller must still be refused rather than reaching it.
    class Explodes(dict):
        def get(self, *a, **k):
            raise AssertionError("looked the agent up before authorising")

    import app as app_module
    real_on_call = app_module.ON_CALL
    app_module.ON_CALL = Explodes()
    try:
        for stranger in ("+15559999999", "", None):
            raw = ({} if stranger is None
                   else {"global_data": {"caller_id_num": stranger}})
            r = agent._execute_swaig_function(
                "coach_agent", {"agent": "dana"}, call_id="sup-1", raw_data=raw)
            assert conference_in(r) is None, (stranger, r)
            assert r["response"].startswith("NOT_AUTHORISED"), (stranger, r)
    finally:
        app_module.ON_CALL = real_on_call

    SUP = sorted(SUPERVISORS)[0]

    # Either location authorises, because which one the platform populates is
    # not settled. Neither is reachable by the model: both come from the
    # platform's post data, not from the tool's arguments.
    for raw in ({"global_data": {"caller_id_num": SUP}},
                {"caller_id_num": SUP}):
        got = conference_in(agent._execute_swaig_function(
            "coach_agent", {"agent": "dana"}, call_id="sup-1", raw_data=raw))
        assert got is not None, raw

    # Coaching a named agent who is on a call.
    r = agent._execute_swaig_function("coach_agent", {"agent": "Dana"},
                                      call_id="sup-1",
                                      raw_data={"global_data": {"caller_id_num": SUP}})
    jc = conference_in(r)
    assert jc is not None, r

    # Joining is the whole of what is emitted: no transfer, no hold, no
    # second verb riding along beside it.
    (action,) = r["action"]
    assert action["SWML"]["sections"]["main"] == [{"join_conference": jc}], action

    # Aimed at one leg. Without coach this is just attendance.
    assert jc["coach"] == ON_CALL["dana"], jc
    assert jc["name"] == ROOM, jc

    # Silent to the room, and unannounced.
    assert jc["muted"] is True, jc
    assert jc["beep"] == "false", jc

    # A supervisor arriving or leaving must not move the customer's call.
    # end_on_exit is absent because the SDK helper omits values equal to the
    # default, and the schema's default is False. start_on_enter defaults to
    # True, so it has to be present and false.
    # absent, not merely false: the SDK omits values at their default and
    # the schema's default is False
    assert "end_on_exit" not in jc, jc
    assert jc["start_on_enter"] is False, jc

    # An agent who is not on a call is refused rather than joined, because
    # joining without a coach target is audible to the customer.
    for missing in ("morgan", "", "  "):
        r = agent._execute_swaig_function("coach_agent", {"agent": missing},
                                          call_id="sup-1",
                                          raw_data={"global_data": {"caller_id_num": SUP}})
        assert conference_in(r) is None, (missing, r)
        assert r["response"].startswith("NOT_ON_A_CALL"), (missing, r)
        # the refusal names who is actually available
        assert "dana" in r["response"], r

    # The other agent is reachable too, so the mapping is real rather than
    # a single hard-coded id.
    r = agent._execute_swaig_function("coach_agent", {"agent": "reza"},
                                      call_id="sup-1",
                                      raw_data={"global_data": {"caller_id_num": SUP}})
    assert conference_in(r)["coach"] == ON_CALL["reza"], r
    assert ON_CALL["dana"] != ON_CALL["reza"]

    print(f"ok: coach={ON_CALL['dana']} into {ROOM!r}, muted with no beep and "
          f"neither starting nor ending the room; an agent not on a call is "
          f"refused")


if __name__ == "__main__":
    main()
