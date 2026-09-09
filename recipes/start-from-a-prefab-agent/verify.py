"""Prove the claim without a network.

Claim: a receptionist and a survey agent each render from a prefab class and
configuration. The prefab supplies the prompt, the tools and their handlers,
and for the receptionist the voice. Your configuration becomes the constraints
the handlers apply.

Proof: build both from app.py's configuration, then render and validate each
document. Assert the tools the prefab registered, the prompt it wrote, the
receptionist's voice, and the questions in global_data with types and scale
intact. Run the handlers and compare exact results. The transfer emits a
connect verb for the configured number with `transfer: "true"`; an unlisted
department is refused; the validator applies the question's scale. Two
constructor behaviours are asserted too: a rating without `scale` defaults to
five, and a multiple choice without `options` raises. The TypeScript prefabs
are held to the same configuration, tools, enum, voice and handler results,
through their own /swaig routes. Expected values live here, not in app.py.
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
USER, PASSWORD = "signalwire", "verify-only-password"
os.environ.setdefault("SWML_BASIC_AUTH_USER", USER)
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", PASSWORD)
os.environ["SALES_NUMBER"] = "+15551230001"
os.environ["WORKSHOP_NUMBER"] = "+15551230002"

# Expected values live here, not imported from app.py.
DEPARTMENTS = ["sales", "workshop"]
WORKSHOP_NUMBER = "+15551230002"
RECEPTION_TOOLS = ["collect_caller_info", "transfer_call"]
RECEPTION_VOICE = "rime.spore"
SURVEY_TOOLS = ["log_response", "validate_response"]
# the TypeScript prefab registers three more, for reading progress
TS_SURVEY_TOOLS = ["answer_question", "get_current_question", "get_survey_progress",
                   "log_response", "validate_response"]
QUESTIONS = [("on_time", "yes_no", None), ("rating", "rating", 5),
             ("notes", "open_ended", None)]
RATING_TEXT = "From one to five, how would you rate the work?"
VALID = "Response to 'rating' is valid."
LOGGED = f"Response to '{RATING_TEXT}' has been recorded."
OUT_OF_SCALE = "Invalid rating. Please provide a number between 1 and 5."
CALLER = {"name": "Dana Whitfield", "reason": "a squeaky brake"}
TRANSFERRED = ("I'll transfer you to our workshop department now. "
               "Thank you for calling, Dana Whitfield!")
REFUSED = "Sorry, I couldn't find the legal department."
TRANSFER_ACTION = {"SWML": {"version": "1.0.0", "sections": {"main": [
    {"connect": {"to": WORKSHOP_NUMBER}}]}}, "transfer": "true"}


def ai_of(agent):
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def ai_in(doc):
    V.validate_swml(doc)
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def main():
    V.sdk_banner()
    from app import BUILDERS

    # --- receptionist -------------------------------------------------------
    rec = BUILDERS["receptionist"]()
    V.assert_basic_auth_from_env(rec)
    ai = ai_of(rec)
    funcs = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert sorted(funcs) == RECEPTION_TOOLS, sorted(funcs)
    # the prefab wrote the prompt, set the voice and its own tuning
    assert ai["prompt"]["pom"], "prefab supplied no prompt sections"
    assert ai["languages"][0]["voice"] == RECEPTION_VOICE, ai["languages"]
    assert ai["params"]["transfer_summary"] is True, ai["params"]
    # your departments became the enum on the transfer tool
    enum = funcs["transfer_call"]["parameters"]["properties"]["department"]["enum"]
    assert enum == DEPARTMENTS, enum
    assert [d["name"] for d in ai["global_data"]["departments"]] == DEPARTMENTS

    raw = {"global_data": ai["global_data"]}
    r = rec._execute_swaig_function("collect_caller_info", dict(CALLER),
                                    call_id="c1", raw_data=raw)
    (action,) = r["action"]
    assert action["set_global_data"]["caller_info"] == CALLER, action

    raw["global_data"]["caller_info"] = {"name": "Dana Whitfield"}
    r = rec._execute_swaig_function("transfer_call", {"department": "workshop"},
                                    call_id="c1", raw_data=raw)
    assert r == {"response": TRANSFERRED, "action": [TRANSFER_ACTION],
                 "post_process": True}, json.dumps(r, indent=1)

    # a department that is not configured is refused, and nothing is dialled
    r = rec._execute_swaig_function("transfer_call", {"department": "legal"},
                                    call_id="c1", raw_data=raw)
    assert r == {"response": REFUSED}, r

    # --- survey -------------------------------------------------------------
    sv = BUILDERS["survey"]()
    V.assert_basic_auth_from_env(sv)
    ai = ai_of(sv)
    assert sorted(f["function"] for f in ai["SWAIG"]["functions"]) == SURVEY_TOOLS
    assert ai["prompt"]["pom"], "prefab supplied no prompt sections"
    assert ai["post_prompt"], "the prefab sets a post_prompt"
    got = [(q["id"], q["type"], q.get("scale")) for q in ai["global_data"]["questions"]]
    assert got == QUESTIONS, got
    assert ai["global_data"]["brand_name"] == "Ridgeline Cycles"

    raw = {"global_data": ai["global_data"]}
    def run(tool, response):
        return sv._execute_swaig_function(
            tool, {"question_id": "rating", "response": response},
            call_id="c1", raw_data=raw)["response"]

    # the scale you configured is the bound the prefab's validator applies
    assert run("validate_response", "7") == OUT_OF_SCALE
    assert run("validate_response", "4") == VALID
    assert run("log_response", "4") == LOGGED

    # what the constructor does with an incomplete question, and with the
    # fourth type this recipe's survey does not use
    from signalwire.prefabs import SurveyAgent
    lax = SurveyAgent(survey_name="s", name="lax", route="/lax", questions=[
        {"id": "r", "type": "rating", "text": "Rate it."},
        {"id": "c", "type": "multiple_choice", "text": "Which shop?",
         "options": ["north", "south"]}])
    qs = ai_of(lax)["global_data"]["questions"]
    assert qs[0]["scale"] == 5, "no default scale"
    assert qs[1]["type"] == "multiple_choice", qs
    assert qs[1]["options"] == ["north", "south"], qs
    try:
        SurveyAgent(survey_name="s", name="bad", route="/bad",
                    questions=[{"id": "c", "type": "multiple_choice", "text": "Pick."}])
    except ValueError as e:
        assert "options" in str(e), e
    else:
        raise AssertionError("a multiple choice question without options was accepted")

    # --- the TypeScript prefabs, held to the same values --------------------
    node = V.node_surface(HERE, env={"SWML_BASIC_AUTH_USER": USER,
                                     "SWML_BASIC_AUTH_PASSWORD": PASSWORD})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        tai = ai_in(node["reception"])
        tfuncs = {f["function"]: f for f in tai["SWAIG"]["functions"]}
        assert sorted(tfuncs) == RECEPTION_TOOLS, sorted(tfuncs)
        assert tai["prompt"].get("text") or tai["prompt"].get("pom"), tai["prompt"]
        assert tai["languages"][0]["voice"] == RECEPTION_VOICE, tai["languages"]
        assert tai["params"]["transfer_summary"] is True, tai["params"]
        assert tfuncs["transfer_call"]["parameters"]["properties"]["department"]["enum"] \
            == DEPARTMENTS
        assert [d["name"] for d in tai["global_data"]["departments"]] == DEPARTMENTS
        (taction,) = node["collected"]["action"]
        assert taction["set_global_data"]["caller_info"] == CALLER, taction
        assert node["transferred"]["response"] == TRANSFERRED, node["transferred"]
        assert node["transferred"]["action"] == [TRANSFER_ACTION], node["transferred"]
        assert node["refused"]["response"] == REFUSED, node["refused"]
        assert "connect" not in json.dumps(node["refused"]), node["refused"]

        sai = ai_in(node["survey"])
        assert sorted(f["function"] for f in sai["SWAIG"]["functions"]) == TS_SURVEY_TOOLS
        assert sai["post_prompt"], "the TypeScript prefab sets a post_prompt"
        tgot = [(q["id"], q["type"], q.get("scale")) for q in sai["global_data"]["questions"]]
        assert tgot == QUESTIONS, tgot
        assert sai["global_data"]["brand_name"] == "Ridgeline Cycles"
        assert node["outOfScale"]["response"] == OUT_OF_SCALE, node["outOfScale"]
        assert node["valid"]["response"] == VALID, node["valid"]
        assert node["logged"]["response"] == LOGGED, node["logged"]
        assert node["laxQuestions"][0]["scale"] == 5, node["laxQuestions"]
        assert node["laxQuestions"][1]["options"] == ["north", "south"], node["laxQuestions"]
        assert "options" in node["missingOptions"], node["missingOptions"]
        ts_note = ("typescript renders the same tools, enum and voice, and its handlers "
                   "return the same transfer, refusal and validation results")

    print(f"ok: receptionist renders {RECEPTION_TOOLS} with voice "
          f"{RECEPTION_VOICE}, transfers to {WORKSHOP_NUMBER} with transfer=true "
          f"and refuses an unlisted department; survey renders {SURVEY_TOOLS} "
          f"over {[q[0] for q in QUESTIONS]} and refuses a rating of 7 on a "
          f"5-point scale; a rating without scale defaults to 5 and a multiple "
          f"choice without options raises; {ts_note}")


if __name__ == "__main__":
    main()
