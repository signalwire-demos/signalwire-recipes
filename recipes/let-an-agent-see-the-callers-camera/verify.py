"""Prove the claim without a network.

Claim: `enable_vision: true` in `ai.params` turns on the platform's
`get_visual_input` function for the agent. `vision_model` names the model, and
an internal filler under `get_visual_input` gives the agent something to say
for it.

Proof: render the agent's SWML. `ai.params` carries `enable_vision: true` and
the `vision_model` the environment set, not the app's default, and the
document validates. The bundled schema documents `enable_vision` with the
sentence naming `get_visual_input`. Its `vision_model` is exactly three named
values plus any string. It lists `get_visual_input` among the internal
fillers. `SWAIG.internal_fillers`
carries exactly the two phrases under that name, and no `get_visual_input`
appears in `SWAIG.functions`, because the platform supplies it. Expected values
live here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")
os.environ["VISION_MODEL"] = "gpt-4.1-nano"   # not app.py's default, so the env must reach it

import verifylib as V  # noqa: E402

LOOKING = ["Let me take a look.", "One moment while I look at that."]


def main():
    V.sdk_banner()
    from app import agent

    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]

    params = ai["params"]
    assert params["enable_vision"] is True, params
    assert params["vision_model"] == "gpt-4.1-nano", params

    fillers = ai["SWAIG"]["internal_fillers"]
    assert fillers == {"get_visual_input": {"en-US": LOOKING}}, fillers
    assert all(f["function"] != "get_visual_input" for f in ai["SWAIG"].get("functions", [])), \
        "get_visual_input is the platform's function, not one the agent defines"
    prompt_text = json.dumps(ai["prompt"]["pom"])
    for phrase in ("on a video call", "look at it before you answer", "describe what you see"):
        assert phrase in prompt_text, (phrase, ai["prompt"])

    # the schema's word on each piece
    defs = V.swml_schema()["$defs"]
    props = defs["AIParams"]["properties"]
    assert "get_visual_input" in props["enable_vision"]["description"], props["enable_vision"]
    assert props["enable_vision"].get("default") is False, props["enable_vision"]
    alternatives = props["vision_model"]["anyOf"]
    named = {alt["const"] for alt in alternatives if "const" in alt}
    assert named == {"gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano"}, named
    assert [alt for alt in alternatives if "const" not in alt] == [{"type": "string"}], alternatives
    filler_names = set(defs["SWAIGInternalFiller"]["properties"])
    assert "get_visual_input" in filler_names, sorted(filler_names)
    native = set(defs["SWAIGNativeFunction"]["enum"])
    assert "get_visual_input" not in native, "the schema lists it as a filler, not a native function"

    print(f"ok: ai.params enable_vision=true, vision_model={params['vision_model']} from the "
          f"environment; SWAIG.internal_fillers covers get_visual_input with {len(LOOKING)} phrases; "
          f"the schema names get_visual_input in enable_vision and among the fillers")


if __name__ == "__main__":
    main()
