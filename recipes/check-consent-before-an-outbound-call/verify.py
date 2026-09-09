"""Prove the claim without a network.

Claim: you place an outbound call only when the number has affirmative
consent on record. The current time must also be inside the permitted window
in the callee's time zone. The check runs in code before the dial.

Proof: the HTTP layer is a recorder. `place()` for a number with no record, a
number that withdrew consent, and a consented number at 21:30 local time each
raise `NoConsent` naming the reason. The recorder sees no request. The same
consented number at 19:00 local time makes exactly one POST to the documented
calling path with exactly the expected body. That instant is 02:00 UTC, outside
the window, so the zone that decides is the callee's. Both ends of the window
are closed, and with no `now` supplied the code reads a frozen clock. A naive
clock raises. Expected values live here, not in app.py.
"""
import json
import os
import pathlib
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SIGNALWIRE_PHONE_NUMBER": "+15550001111",
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
OK, WITHDRAWN, UNKNOWN = "+15557654321", "+15550009999", "+15550001234"
# 04:30 UTC is 21:30 the previous evening in Los Angeles, outside the window;
# 02:00 UTC is 19:00 there, inside it, while 02:00 itself is outside. The
# second instant only passes if the callee's zone is the one that decides.
LA = ZoneInfo("America/Los_Angeles")
WINDOW = (time(9, 0), time(20, 0))
LATE = datetime(2026, 9, 2, 4, 30, tzinfo=ZoneInfo("UTC"))
EVENING = datetime(2026, 9, 2, 2, 0, tzinfo=ZoneInfo("UTC"))
assert LATE.astimezone(LA).time() == time(21, 30)
assert EVENING.astimezone(LA).time() == time(19, 0)
assert not WINDOW[0] <= EVENING.time() <= WINDOW[1], "the instant must be outside the window in UTC"


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    for number, when, reason in [(UNKNOWN, EVENING, "no consent on record"),
                                 (WITHDRAWN, EVENING, "consent withdrawn"),
                                 (OK, LATE, "outside the calling window, it is 21:30")]:
        try:
            recipe.place(number, "hello", now=when)
        except recipe.NoConsent as e:
            assert reason in str(e), (number, str(e))
        else:
            raise AssertionError(f"{number} at {when} was dialled")
        assert rec.calls == [], rec.calls  # the check ran before any request

    # the window is the callee's local time: 02:00 UTC is 19:00 in Los Angeles
    assert recipe.allowed(OK, EVENING) is None
    assert "21:30" in recipe.allowed(OK, LATE)
    try:
        recipe.allowed(OK, EVENING.replace(tzinfo=None))
    except ValueError:
        pass
    else:
        raise AssertionError("a naive clock was accepted")

    # both ends of the window are closed: the edges pass, one minute past fails
    def la(hour, minute):
        return datetime(2026, 9, 2, hour, minute, tzinfo=LA).astimezone(ZoneInfo("UTC"))

    for hour, minute in ((9, 0), (20, 0)):
        assert recipe.allowed(OK, la(hour, minute)) is None, (hour, minute)
    for hour, minute in ((8, 59), (20, 1)):
        reason = recipe.allowed(OK, la(hour, minute))
        assert reason and f"{hour:02d}:{minute:02d}" in reason, (hour, minute, reason)
        try:
            recipe.place(OK, "hello", now=la(hour, minute))
        except recipe.NoConsent:
            pass
        else:
            raise AssertionError(f"{hour:02d}:{minute:02d} was dialled")
    assert rec.calls == [], rec.calls

    # with no `now`, the code reads the clock itself
    class FrozenDatetime(datetime):
        frozen = LATE

        @classmethod
        def now(cls, tz=None):
            return cls.frozen.astimezone(tz) if tz else cls.frozen

    real_datetime = recipe.datetime
    recipe.datetime = FrozenDatetime
    try:
        try:
            recipe.place(OK, "hello")
        except recipe.NoConsent as e:
            assert "21:30" in str(e), str(e)
        else:
            raise AssertionError("a frozen late clock was dialled")
        assert rec.calls == [], rec.calls
        FrozenDatetime.frozen = EVENING
        recipe.place(OK, "Your bike is ready.")
        assert len(rec.calls) == 1, rec.calls
        rec.calls.clear()
    finally:
        recipe.datetime = real_datetime

    recipe.place(OK, "Your bike is ready.", now=EVENING)
    assert len(rec.calls) == 1, rec.calls
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", PATH), call
    body = call["body"]
    # the whole request, not a field of it
    assert body == {"command": "dial", "params": {
        "from": "+15550001111", "to": OK, "timeout": 25,
        "swml": {"version": "1.0.0", "sections": {"main": [
            {"answer": {}}, {"play": {"url": "say:Your bike is ready."}}, {"hangup": {}}]}},
    }}, json.dumps(body, indent=1)
    params = body["params"]
    V.assert_documented("rest", "POST", PATH, None)
    schema = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    assert set(params) <= set(schema["properties"]), sorted(set(params) - set(schema["properties"]))
    assert set(schema.get("required", [])) <= set(params), schema.get("required")
    V.validate_swml(params["swml"])

    print(f"ok: no record, withdrawn consent, 21:30 local, 08:59 and 20:01 each raised "
          f"NoConsent with no request; 09:00 and 20:00 pass. The consented number at 19:00 "
          f"local (02:00 UTC) made one POST {PATH} command=dial with the expected body.")


if __name__ == "__main__":
    main()
