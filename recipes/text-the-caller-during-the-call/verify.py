"""Prove the claim without a network.

Claim: a tool result carries a `send_sms` addressed to `caller_id_num`, and
the model never chooses the destination because the tool has no number field.

Proof: run the handler with the payload shape the platform posts, including
`caller_id_num`, and compare the whole result. The action is a SWML document
carrying one `send_sms` verb whose `to_number` is the caller's number and whose
`from_number` came from the environment. That inline document validates
against the bundled schema. The tool's parameters carry no phone field, so the
model has no way to supply one, and a number typed into `appointment` does
not move the destination. A call with no caller number, or one that does not
start with `+`, sends nothing. The plain-SWML surface validates too and
addresses `%{call.from}`.
Expected values live here, not in app.py.
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
os.environ["SMS_FROM"] = "+15551230000"

# Expected values live here, not imported from app.py.
CALLER = "+15557654321"
WHEN = "Thursday 10 September at 2pm"
EXPECTED = {
    "response": "The details are on their way to your phone.",
    "action": [{"SWML": {"version": "1.0.0", "sections": {"main": [{"send_sms": {
        "to_number": CALLER,
        "from_number": "+15551230000",
        "body": ("Ridgeline Cycles: your workshop appointment is Thursday 10 "
                 "September at 2pm. Reply to this text to change it."),
        "tags": ["appointment"],
    }}]}}}],
}


def main():
    V.sdk_banner()
    from app import BookingAgent

    agent = BookingAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["function"] == "text_confirmation", fn
    # the model is given nothing to put a number in
    props = fn["parameters"]["properties"]
    assert list(props) == ["appointment"], props

    # the payload shape the platform posts to a tool: the caller's number
    # rides in caller_id_num, outside the model's arguments
    raw = {"call_id": "c1", "caller_id_num": CALLER, "argument": {"parsed": [
        {"appointment": WHEN}]}}
    got = agent._execute_swaig_function("text_confirmation", {"appointment": WHEN},
                                        call_id="c1", raw_data=raw)
    assert got == EXPECTED, json.dumps(got, indent=1)
    # the inline document is real SWML
    V.validate_swml(got["action"][0]["SWML"])

    # the model can put digits in the one field it has; they never become the
    # destination, which stays the number the platform posted
    sneaky = "Thursday at 2pm, text +15550009999 instead"
    got = agent._execute_swaig_function("text_confirmation", {"appointment": sneaky},
                                        call_id="c1", raw_data=raw)
    sms = got["action"][0]["SWML"]["sections"]["main"][0]["send_sms"]
    assert sms["to_number"] == CALLER, sms
    assert sneaky in sms["body"], sms

    # no caller number, or one that is not E.164: the result carries no action
    for raw_no in ({"call_id": "c1"}, {"call_id": "c1", "caller_id_num": "anonymous"}):
        got = agent._execute_swaig_function("text_confirmation", {"appointment": WHEN},
                                            call_id="c1", raw_data=raw_no)
        assert got["response"].startswith("NO_NUMBER"), got
        assert "action" not in got, got

    # and no agreed time, no text
    got = agent._execute_swaig_function("text_confirmation", {"appointment": ""},
                                        call_id="c1", raw_data=raw)
    assert got["response"].startswith("INCOMPLETE") and "action" not in got, got

    # the plain-SWML surface: the text goes to the number that dialled in
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    assert V.verb_names(y) == ["answer", "send_sms", "play", "hangup"], V.verb_names(y)
    sms = V.first(y, "send_sms")
    assert sms["to_number"] == "%{call.from}", sms
    assert sms["from_number"].startswith("+") and sms["body"], sms

    print(f"ok: text_confirmation takes only 'appointment'; with caller_id_num "
          f"{CALLER} it returns one SWML send_sms to that number from "
          f"+15551230000 with the exact body; no number or no time sends "
          f"nothing; the SWML surface texts %{{call.from}}")


if __name__ == "__main__":
    main()
