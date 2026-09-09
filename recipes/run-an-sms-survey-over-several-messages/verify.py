"""Prove the claim without a network.

Claim: a survey runs across several inbound messages with the state kept by
the sender's number. Each reply advances one step and is answered with a
messaging SWML `reply`; an answer that does not fit is re-asked; STOP ends the
survey and a stopped number is never texted a first question; the webhook
refuses an unsigned request before touching state.

Proof: the handler is driven with the documented inbound-message payload, one
reply at a time, and the state file is read back between turns. The first
question goes out through a recorder as one documented messaging send. The
Flask app is driven with a signed and an unsigned request. The state file is
reloaded through a fresh import between the two halves, because the documented
commands are two processes. The TypeScript surface runs the same conversation
and is held to the same replies and the same state. Expected values live here,
not in app.py.
"""
import hashlib
import hmac
import importlib
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
STATE = pathlib.Path(tempfile.mkdtemp()) / "survey-state.json"
FROM, KEY, URL = "+15550001111", "sign-me", "https://survey.example.com/inbound"
ADMIN = "start-surveys"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SMS_FROM": FROM,
    "SIGNALWIRE_SIGNING_KEY": KEY,
    "INBOUND_URL": URL,
    "SURVEY_STATE_PATH": str(STATE),
    "SURVEY_ADMIN_KEY": ADMIN,
})

import verifylib as V  # noqa: E402

MESSAGES = "/api/messaging/messages"
CUSTOMER = "+14155550123"
OTHER = "+14155550999"
Q1 = ("Thanks for visiting Ridgeline Cycles. How was your service today? "
      "Reply with a number from 1 to 5.")
Q2 = "Would you recommend us to a friend? Reply YES or NO."
Q3 = "Anything we should know? Reply with a sentence, or SKIP."
DONE = "That is everything. Thank you. Reply STOP at any time to opt out."
REASK_SCALE = "Please reply with a single number from 1 to 5."
STOPPED = "You will receive no more messages from Ridgeline Cycles."


COUNTER = [0]


def inbound(sender, body, message_id=None):
    """The documented inbound-message payload, with every required key."""
    COUNTER[0] += 1
    return {"message": {"message_id": message_id or f"m-{COUNTER[0]}",
                        "project_id": "proj-1234",
                        "space_id": "sp-1", "direction": "inbound", "type": "sms",
                        "from": sender, "to": FROM, "body": body, "media": [],
                        "segments": 1, "timestamp": "2026-09-04T09:00:00Z"},
            "vars": {}, "params": {}}


def text_of(doc):
    """The one reply in a messaging document.

    The bundled schema is the voice schema and carries no messaging verbs, so
    the shape is asserted: one step, one `reply`, one `body` (docs:
    swml/reference/messaging/reply)."""
    assert doc["version"] == "1.0.0" and set(doc) == {"version", "sections"}, doc
    (step,) = doc["sections"]["main"]
    assert set(step) == {"reply"} and set(step["reply"]) == {"body"}, step
    return step["reply"]["body"]


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"id": "msg-1", "status": "queued"}])
    recipe.http = rec

    # the first question is one documented send, and it sets the state
    recipe.begin(CUSTOMER)
    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", MESSAGES)], rec.calls
    body = rec.calls[0]["body"]
    assert body == {"to": CUSTOMER, "from": FROM, "body": Q1}, body
    V.assert_documented("rest", "POST", MESSAGES, body)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert state == {CUSTOMER: {"step": 0, "answers": {}, "stopped": False}}, state

    # the webhook is a second process: reload so nothing is carried in memory
    recipe = importlib.reload(recipe)
    recipe.http = rec

    # a wrong answer is re-asked and does not advance; a right one advances
    assert text_of(recipe.handle_inbound(inbound(CUSTOMER, "great")["message"])) == REASK_SCALE
    assert json.loads(STATE.read_text(encoding="utf-8"))[CUSTOMER]["step"] == 0
    assert text_of(recipe.handle_inbound(inbound(CUSTOMER, " 4 ")["message"])) == Q2
    assert text_of(recipe.handle_inbound(inbound(CUSTOMER, "Yes")["message"])) == Q3
    assert text_of(recipe.handle_inbound(inbound(CUSTOMER, "Friendly staff")["message"])) == DONE
    state = json.loads(STATE.read_text(encoding="utf-8"))
    seen = state[CUSTOMER].pop("seen")
    assert state[CUSTOMER] == {"step": 3, "stopped": False,
                               "answers": {"rating": 4, "recommend": True,
                                           "comment": "Friendly staff"}}, state
    # the record remembers every message it acted on, and what it answered
    assert seen == {"m-2": Q2, "m-3": Q3, "m-4": DONE}, seen
    state[CUSTOMER]["seen"] = seen

    # after the last question, a stray text is silence: nothing sent, nothing kept
    doc = recipe.handle_inbound(inbound(CUSTOMER, "hello?")["message"])
    V.validate_swml(doc)  # an empty main is plain SWML, and it validates
    assert doc["sections"]["main"] == [], doc
    assert json.loads(STATE.read_text(encoding="utf-8")) == state

    # a number not in a survey gets silence too
    doc = recipe.handle_inbound(inbound(OTHER, "4")["message"])
    assert doc["sections"]["main"] == [], doc
    assert OTHER not in json.loads(STATE.read_text(encoding="utf-8"))

    # the same message delivered twice: the second copy gets the same reply and
    # changes nothing, or a repeated YES would land in the comment box
    dup = "+14155550777"
    recipe.begin(dup)
    rating = inbound(dup, "4", "dup-0")["message"]
    yes = inbound(dup, "Yes", "dup-1")["message"]
    assert text_of(recipe.handle_inbound(rating)) == Q2
    assert text_of(recipe.handle_inbound(yes)) == Q3
    before = json.loads(STATE.read_text(encoding="utf-8"))[dup]
    assert text_of(recipe.handle_inbound(yes)) == Q3
    # a late retry of the rating, after the survey moved on: it must not be
    # parsed at the comment step and stored as the comment
    assert text_of(recipe.handle_inbound(rating)) == Q2
    assert json.loads(STATE.read_text(encoding="utf-8"))[dup] == before
    assert before["step"] == 2 and before["answers"] == {"rating": 4, "recommend": True}
    # a retry of the final answer, after the survey is complete, gets DONE again
    comment = inbound(dup, "Quick service", "dup-2")["message"]
    assert text_of(recipe.handle_inbound(comment)) == DONE
    finished = json.loads(STATE.read_text(encoding="utf-8"))[dup]
    assert text_of(recipe.handle_inbound(comment)) == DONE
    assert json.loads(STATE.read_text(encoding="utf-8"))[dup] == finished
    assert finished["answers"]["comment"] == "Quick service"
    assert set(finished["seen"]) == {"dup-0", "dup-1", "dup-2"}, finished["seen"]

    # answer, STOP, then a late retry of the answer: silence, not the cached
    # next question, because that number opted out in between
    quiet = "+14155550666"
    recipe.begin(quiet)
    first = inbound(quiet, "5", "late-0")["message"]
    assert text_of(recipe.handle_inbound(first)) == Q2
    assert text_of(recipe.handle_inbound(inbound(quiet, "STOP")["message"])) == STOPPED
    doc = recipe.handle_inbound(first)
    assert doc["sections"]["main"] == [], doc
    assert json.loads(STATE.read_text(encoding="utf-8"))[quiet]["stopped"] is True

    # STOP ends it, and a stopped number is refused a first question, no request
    rec2 = V.Recorder()
    recipe.http = rec2
    recipe.begin(OTHER)
    assert len(rec2.calls) == 1
    assert text_of(recipe.handle_inbound(inbound(OTHER, "STOP")["message"])) == STOPPED
    assert json.loads(STATE.read_text(encoding="utf-8"))[OTHER]["stopped"] is True
    try:
        recipe.begin(OTHER)
    except recipe.OptedOut as exc:
        assert OTHER in str(exc), exc
    else:
        raise AssertionError("a stopped number was texted")
    assert len(rec2.calls) == 1, rec2.calls

    # the route refuses an unsigned request before touching state, and answers
    # a signed one
    with recipe.app.test_client() as web:
        raw = json.dumps(inbound(OTHER, "4")).encode()
        forged = web.post("/inbound", data=raw, content_type="application/json")
        assert forged.status_code == 403, forged.status_code
        sig = hmac.new(KEY.encode(), URL.encode() + raw, hashlib.sha1).hexdigest()
        real = web.post("/inbound", data=raw, content_type="application/json",
                        headers={"X-Signalwire-Signature": sig})
        assert real.status_code == 200, real.status_code
        # OTHER had stopped, so even a signed reply gets an empty document
        assert real.get_json()["sections"]["main"] == [], real.get_json()

        # /begin spends money with your credentials, so it wants the server's
        # key: no key and a wrong key are refused with no request made
        rec3 = V.Recorder(responses=[{"id": "msg-2"}])
        recipe.http = rec3
        target = {"to": "+14155550555"}
        assert web.post("/begin", json=target).status_code == 403
        assert web.post("/begin", json=target,
                        headers={"X-Survey-Key": "nope"}).status_code == 403
        assert rec3.calls == [], rec3.calls
        ok = web.post("/begin", json=target, headers={"X-Survey-Key": ADMIN})
        assert ok.status_code == 200, ok.status_code
        assert len(rec3.calls) == 1, rec3.calls

    # the TypeScript surface runs the same conversation from an empty file
    node = V.node_surface(HERE, CUSTOMER, OTHER, env={
        "SMS_FROM": FROM, "SIGNALWIRE_SIGNING_KEY": KEY, "INBOUND_URL": URL,
        "SURVEY_ADMIN_KEY": ADMIN})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["sent"] == [{"method": "POST", "path": MESSAGES,
                                 "body": {"to": CUSTOMER, "from": FROM, "body": Q1}}], node
        assert node["replies"] == [REASK_SCALE, Q2, Q3, DONE, None, None, STOPPED], node
        ts_seen = node["state"][CUSTOMER].pop("seen")
        assert node["state"][CUSTOMER] == {"step": 3, "stopped": False,
                                           "answers": {"rating": 4, "recommend": True,
                                                       "comment": "Friendly staff"}}
        assert ts_seen == {"m-2": Q2, "m-3": Q3, "m-4": DONE}, ts_seen
        assert node["state"][OTHER]["stopped"] is True
        assert node["refusedBegin"] is True, node
        assert node["signature"] == {"forged": 403, "signed": 200}, node
        assert node["redelivery"] == {"first": Q2, "second": Q3, "again": Q3,
                                      "late": Q2, "done": DONE, "doneAgain": DONE,
                                      "afterStop": None}, node
        assert node["begin"] == {"noKey": 403, "wrongKey": 403, "sentAfterRefusals": 0,
                                 "withKey": 200, "sentWithKey": 1}, node
        ts_note = ("typescript runs the same turns to the same replies and state, "
                   "answers a redelivered message without moving, refuses the same "
                   "begin, gates the same signature, and refuses /begin without the key")

    print(f"ok: begin sends one documented POST {MESSAGES} and records step 0; a "
          f"reload later, four replies advance the survey through re-ask, 4, YES "
          f"and a comment to the closing line, with the answers on disk; a stray "
          f"text and an unknown number get an empty document; STOP marks the "
          f"number and a second begin is refused with no request; the route "
          f"refuses an unsigned POST with 403 and answers a signed one; a redelivered "
          f"message gets the same reply and changes nothing, a late retry too, and a "
          f"retried final answer gets the closing line again, while a retry after STOP "
          f"gets silence; /begin refuses a missing "
          f"or wrong key with no request and sends with the right one; {ts_note}")


if __name__ == "__main__":
    main()
