"""Prove the claim without a network.

Claim: a tool handler turns the words speech recognition produces for a date
and a phone number into an ISO date and an E.164 number, writes those to
`global_data`, reads both back in words the caller can check, and answers with
a typed state when it cannot. The model converts nothing.

Proof: with today pinned to Saturday 2026-09-05, twelve (date, phone) pairs go
through the handler and every response and action is compared to a table kept
here: relative days, bare and "next" weekdays, ordinal words, a numeric date,
a date that does not exist, and a seven digit number. The TypeScript surface
runs the same table through its /swaig route and must match the same table.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

USER, PASSWORD = "signalwire", "verify-only-password"
os.environ.setdefault("SWML_BASIC_AUTH_USER", USER)
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", PASSWORD)
TODAY = "2026-09-05"          # a Saturday
os.environ["TODAY"] = TODAY

PHONE = "+14155550123"
SPOKEN_PHONE = "four one five, five five five, zero one two three"
CONFIRM = ". Read both back and ask the caller to confirm."


def ok(iso, spoken):
    return {"response": f"Callback set for {spoken} at {SPOKEN_PHONE}{CONFIRM}",
            "action": [{"set_global_data": {"callback": {"date": iso, "phone": PHONE}}}]}


def bad_date(text):
    return {"response": f"UNPARSED_DATE: could not read '{text}' as a date. Ask the "
                        "caller for the day and the month, then call again."}


def bad_phone(text):
    return {"response": f"UNPARSED_PHONE: '{text}' was not a ten digit number. "
                        "Ask the caller to say it digit by digit, then call again."}


# (date as spoken, phone as spoken) -> the exact result, both surfaces
CASES = [
    (("tomorrow", "four one five five five five oh one two three"),
     ok("2026-09-06", "Sunday, September 6th")),
    (("today", "4155550123"), ok("2026-09-05", "Saturday, September 5th")),
    (("Tuesday", "1 415 555 0123"), ok("2026-09-08", "Tuesday, September 8th")),
    # today is a Saturday: a bare weekday is the next one, not today
    (("Saturday", "4155550123"), ok("2026-09-12", "Saturday, September 12th")),
    (("next Tuesday", "(415) 555-0123"), ok("2026-09-15", "Tuesday, September 15th")),
    (("the fifth of March", "415.555.0123"), ok("2027-03-05", "Friday, March 5th")),
    (("March 5th", "four one five, five five five, oh one two three"),
     ok("2027-03-05", "Friday, March 5th")),
    (("September 30", "415-555-0123"), ok("2026-09-30", "Wednesday, September 30th")),
    (("9/30", "4155550123"), ok("2026-09-30", "Wednesday, September 30th")),
    (("the twenty second of September", "4155550123"),
     ok("2026-09-22", "Tuesday, September 22nd")),
    (("someday soon", "4155550123"), bad_date("someday soon")),
    (("February 30", "4155550123"), bad_date("February 30")),
    (("tomorrow", "five five five oh one two three"),
     bad_phone("five five five oh one two three")),
]


def check_tool(fn, label):
    """The one tool, with the spoken examples in its parameter descriptions."""
    assert fn["function"] == "schedule_callback", (label, fn)
    assert fn["parameters"]["required"] == ["date", "phone"], (label, fn["parameters"])
    props = fn["parameters"]["properties"]
    # the descriptions carry the examples; the conversion is the handler's
    assert "next Tuesday" in props["date"]["description"], (label, props["date"])
    assert "oh one two three" in props["phone"]["description"], (label, props["phone"])


def check(results, label):
    assert len(results) == len(CASES), (label, len(results))
    for ((date_text, phone_text), want), got in zip(CASES, results):
        assert got.get("response") == want["response"], (label, date_text, phone_text,
                                                         got.get("response"))
        assert (got.get("action") or []) == want.get("action", []), (label, date_text,
                                                                     got.get("action"))


def main():
    V.sdk_banner()
    from app import CallbackDesk

    agent = CallbackDesk()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    (fn,) = ai["SWAIG"]["functions"]
    check_tool(fn, "python")

    results = [agent._execute_swaig_function("schedule_callback",
                                             {"date": d, "phone": p}, call_id="c1")
               for (d, p), _want in CASES]
    check(results, "python")

    cases = json.dumps([{"date": d, "phone": p} for (d, p), _ in CASES])
    node = V.node_surface(HERE, cases, env={"SWML_BASIC_AUTH_USER": USER,
                                            "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                                            "TODAY": TODAY})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        V.validate_swml(node["doc"])
        tai = next(v for v in node["doc"]["sections"]["main"] if "ai" in v)["ai"]
        (tfn,) = tai["SWAIG"]["functions"]
        check_tool(tfn, "typescript")
        check(node["results"], "typescript")
        ts_note = "typescript gives the same thirteen results through its /swaig route"

    print(f"ok: with today {TODAY}, ten spoken dates and numbers become ISO dates and "
          f"{PHONE} in set_global_data and are read back as words; 'someday soon', "
          f"'February 30' and a seven digit number get typed UNPARSED states; {ts_note}")


if __name__ == "__main__":
    main()
