"""Prove the claim without a network.

Claim: the qualification fields of the disposition come from what the tool
handlers wrote to `global_data`, not from the transcript or the model's
summary. Identifiers come from the POST envelope; the summary is a note.

Proof: run each handler and assert the `set_global_data` action it emits, and
that an invalid value writes nothing. Render the document and assert
`post_prompt` and `post_prompt_url` are present, so the platform will POST at
the end of the call. Then POST to the agent's own /post_prompt route with the
platform's payload shape. `global_data` carries what the handlers wrote; the
`post_prompt_data` summary and the `call_log` transcript contradict all three
fields. The qualification fields equal the handler fields, and the model's
words appear only as the note. A second POST whose `global_data` lacks a field
marks the record incomplete.
Expected values live here, not in app.py.
"""
import base64
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
os.environ["MIN_BUDGET"] = "5000"

# Expected values live here, not imported from app.py.
TOOLS = ["record_budget", "record_decision_maker", "record_timeline"]
HANDLER_DATA = {"budget": 12000, "timeline_weeks": 6, "can_sign": True}
# the summary and the transcript disagree with every handler-written field
MODEL_STORY = ("The caller has a budget of two million dollars, needs the bikes "
               "next week, and cannot sign without their director.")
TRANSCRIPT = [{"role": "user", "content": "Two million, next week, and my director signs."},
              {"role": "assistant", "content": "Two million, one week, director to sign."}]


def basic_auth():
    raw = f"{os.environ['SWML_BASIC_AUTH_USER']}:{os.environ['SWML_BASIC_AUTH_PASSWORD']}"
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}


def post_prompt_body(global_data, raw_summary):
    """The shape the platform POSTs to post_prompt_url at the end of a call."""
    return {"call_id": "c1", "action": "post_conversation",
            "caller_id_number": "+15557654321",
            "global_data": global_data, "call_log": TRANSCRIPT,
            "post_prompt_data": {"raw": raw_summary, "parsed": [],
                                 "substituted": raw_summary}}


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    import app as recipe

    agent = recipe.agent
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml(call_id="c1"))
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    assert sorted(f["function"] for f in ai["SWAIG"]["functions"]) == TOOLS
    # the end-of-call POST is wired: a post_prompt and a URL to receive it
    assert ai["post_prompt"]["text"], ai.get("post_prompt")
    full = ai["post_prompt_url"]
    url = full.split("?")[0].rstrip("/")
    assert url.endswith("/qualifier/post_prompt"), url
    # the URL the SDK builds carries the basic-auth credentials and a token
    assert "@" in full.split("//", 1)[1].split("/")[0], "no credentials in post_prompt_url"
    assert "__token=" in full, full

    # --- handlers write global_data, and refuse what does not parse -----------
    def run(tool, **args):
        return agent._execute_swaig_function(tool, args, call_id="c1")

    assert run("record_budget", amount=12000)["action"] == [
        {"set_global_data": {"budget": 12000}}]
    assert run("record_timeline", weeks=6)["action"] == [
        {"set_global_data": {"timeline_weeks": 6}}]
    assert run("record_decision_maker", can_sign=True)["action"] == [
        {"set_global_data": {"can_sign": True}}]
    for tool, args in [("record_budget", {"amount": "lots"}),
                       ("record_budget", {"amount": -5}),
                       ("record_budget", {"amount": True}),  # bool is an int
                       ("record_timeline", {"weeks": "soon"}),
                       ("record_timeline", {"weeks": -1}),
                       ("record_timeline", {"weeks": False}),
                       ("record_decision_maker", {"can_sign": "yes"})]:
        r = run(tool, **args)
        assert r["response"].startswith("INVALID") and "action" not in r, (tool, r)

    # --- the end-of-call POST: the disposition comes from global_data ---------
    client = TestClient(agent.get_app())
    path = agent.route + "/post_prompt"
    del recipe.DISPOSITIONS[:]

    r = client.post(path, json=post_prompt_body(HANDLER_DATA, MODEL_STORY))
    assert r.status_code == 401, r.status_code  # basic auth gates the route
    assert recipe.DISPOSITIONS == []

    r = client.post(path, json=post_prompt_body(HANDLER_DATA, MODEL_STORY),
                    headers=basic_auth())
    assert r.status_code == 200 and r.json() == {"success": True}, (r.status_code, r.text)
    (d,) = recipe.DISPOSITIONS
    # the transcript and the summary both say two million; the qualification
    # fields say what the handlers wrote, and the summary is only the note
    assert d == {
        "call_id": "c1", "caller": "+15557654321",
        "budget": 12000, "timeline_weeks": 6, "can_sign": True,
        "qualified": True, "complete": True,
        "model_note": MODEL_STORY,
    }, json.dumps(d, indent=1)

    # a call where a handler never ran: the field is absent, and the code
    # says so rather than filling it from the summary
    partial = {"budget": 3000, "timeline_weeks": 2}
    r = client.post(path, json=post_prompt_body(partial, "They can sign today."),
                    headers=basic_auth())
    assert r.status_code == 200
    d = recipe.DISPOSITIONS[-1]
    assert (d["can_sign"], d["qualified"], d["complete"]) == (None, False, False), d

    print(f"ok: {TOOLS} write set_global_data and refuse bad values; the "
          f"document carries post_prompt and post_prompt_url; a post_prompt POST "
          f"yields a disposition equal to the handler fields with the model's "
          f"contradicting summary kept only as a note; a missing field marks the "
          f"record incomplete")


if __name__ == "__main__":
    main()
