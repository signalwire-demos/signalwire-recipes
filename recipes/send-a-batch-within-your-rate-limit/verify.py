"""Prove the claim without a network.

Claim: a batch goes out one message per interval for the number type's
documented rate. Requests start at the published nominal interval; delivery
is the platform's side.

Proof: the HTTP layer is a recorder, and the clock and sleep are a fake clock
that advances only when the pacer sleeps. Ten messages at the 10DLC rate of 4
per second make ten POSTs to the documented messages path, each with exactly
`to`, `from` and `body`. The clock reads at the ten sends are 0.25 seconds
apart, so the batch takes 2.25 seconds of fake time, and no send is early. At
the toll-free rate the spacing is one third of a second. A sleep that
overshoots, and a platform that answers slowly, never let two sends bunch up.
An unknown number type raises before any request. The rates are the
verifier's own numbers, taken from the rate limits page, and must equal the
app's. Expected values live here, not in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SMS_FROM": "+15550001111",
    "NUMBER_TYPE": "10dlc",
})

import verifylib as V  # noqa: E402

MESSAGES = "/api/messaging/messages"
# https://signalwire.com/docs/platform/rate-limits, fetched 2026-09-02
RATES = {"10dlc": 4, "toll-free": 3, "short-code": 10}
BODY = "Your bike is ready for pickup."


class FakeClock:
    """Time that moves only when the pacer sleeps."""

    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        assert seconds > 0, seconds
        self.sleeps.append(round(seconds, 6))
        self.now += seconds


def paced_run(recipe, number_type, count):
    clock = FakeClock()
    rec = V.Recorder(responses=[{"id": f"m{i}", "status": "queued"} for i in range(count)])
    stamps = []
    real_post = rec.post

    def stamped_post(path, body=None, params=None):
        stamps.append(clock.now)
        return real_post(path, body, params)

    rec.post = stamped_post
    recipe.http = rec
    recipients = [f"+1555010{i:04d}" for i in range(count)]
    results = recipe.send_batch(recipients, BODY, number_type,
                                clock=clock.clock, sleep=clock.sleep)
    return rec, clock, stamps, recipients, results


def main():
    V.sdk_banner()
    import app as recipe

    assert recipe.LIMITS == RATES, recipe.LIMITS

    # ten messages at 4 per second: 0.25 s apart, 2.25 s of fake time
    rec, clock, stamps, recipients, results = paced_run(recipe, "10dlc", 10)
    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", MESSAGES)] * 10
    assert [c["body"] for c in rec.calls] == \
        [{"to": to, "from": "+15550001111", "body": BODY} for to in recipients]
    V.assert_documented("rest", "POST", MESSAGES, rec.calls[0]["body"])
    gaps = [round(b - a, 6) for a, b in zip(stamps, stamps[1:])]
    assert gaps == [0.25] * 9, gaps
    assert round(stamps[-1] - stamps[0], 6) == 2.25, stamps
    assert clock.sleeps == [0.25] * 9, clock.sleeps
    assert [r["id"] for r in results] == [f"m{i}" for i in range(10)], results

    # a sleep that overshoots must not let the next send land early (codex,
    # wave 10 review): the pacer re-reads the clock after sleeping
    late = FakeClock()
    real_sleep = late.sleep
    late.sleep = lambda seconds: real_sleep(seconds + 0.05)
    rec2 = V.Recorder(responses=[{"id": f"m{i}", "status": "queued"} for i in range(5)])
    stamps2 = []
    real_post2 = rec2.post

    def stamped_post2(path, body=None, params=None):
        stamps2.append(late.now)
        return real_post2(path, body, params)

    rec2.post = stamped_post2
    recipe.http = rec2
    recipe.send_batch([f"+1555020{i:04d}" for i in range(5)], BODY, "10dlc",
                      clock=late.clock, sleep=late.sleep)
    gaps2 = [round(b - a, 6) for a, b in zip(stamps2, stamps2[1:])]
    assert all(g >= 0.25 for g in gaps2), gaps2
    assert gaps2 == [0.3] * 4, gaps2

    # the toll-free rate spaces them a third of a second apart
    _, _, stamps, _, _ = paced_run(recipe, "toll-free", 4)
    gaps = [round(b - a, 4) for a, b in zip(stamps, stamps[1:])]
    assert gaps == [0.3333] * 3, gaps

    # a platform that answers slowly: the next send follows the answer, and
    # the pacer never bunches sends up to catch up (sol r1)
    slow = FakeClock()
    rec4 = V.Recorder(responses=[{"id": f"m{i}", "status": "queued"} for i in range(5)])
    stamps4 = []
    real_post4 = rec4.post

    def slow_post(path, body=None, params=None):
        stamps4.append(slow.now)
        slow.now += 0.4                     # the request itself takes longer than the interval
        return real_post4(path, body, params)

    rec4.post = slow_post
    recipe.http = rec4
    recipe.send_batch([f"+1555030{i:04d}" for i in range(5)], BODY, "10dlc",
                      clock=slow.clock, sleep=slow.sleep)
    gaps4 = [round(b - a, 6) for a, b in zip(stamps4, stamps4[1:])]
    assert gaps4 == [0.4] * 4, gaps4
    assert slow.sleeps == [], slow.sleeps    # nothing to wait for; nothing to catch up either

    # an unknown type: refused before any request
    rec = V.Recorder()
    recipe.http = rec
    for kwargs, fragment in (({"recipients": ["+15550100000"], "number_type": "pager"},
                              "number_type must be one of"),):
        try:
            recipe.send_batch(kwargs["recipients"], BODY, kwargs["number_type"],
                              clock=lambda: 0.0, sleep=lambda s: None)
        except ValueError as e:
            assert fragment in str(e), str(e)
        else:
            raise AssertionError(f"{kwargs['number_type']} batch was not refused")
    assert rec.calls == [], rec.calls

    print(f"ok: 10 messages at 4 MPS went out 0.25 s apart over 2.25 s of fake time, each a "
          f"documented POST {MESSAGES}; toll-free spaces at 1/3 s; a 10,001 batch and an unknown "
          f"number type are refused with no request")


if __name__ == "__main__":
    main()
