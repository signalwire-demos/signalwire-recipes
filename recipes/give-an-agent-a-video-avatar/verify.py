"""Prove the claim without a network.

Claim: three `ai.params`, `video_idle_file`, `video_listening_file` and
`video_talking_file`, give an agent a face on a video call, and the schema
names the state each one plays for.

Proof: render the agent's SWML and read `ai.params`. The three keys hold
exactly the three expected URLs and no other `video_*` key is present. The
plain-SWML surface validates and carries the same three. The bundled schema
documents each key under `AIParams` with its state in the description and the
note that it only works for calls that support video. The schema accepts a
misspelt key without complaint, so the exact-key assertions are the guard.
Expected values live here, not in app.py.
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
os.environ["AVATAR_BASE_URL"] = "https://media.example.com/avatar"

import verifylib as V  # noqa: E402

EXPECTED = {
    "video_idle_file": "https://media.example.com/avatar/idle.mp4",
    "video_listening_file": "https://media.example.com/avatar/listening.mp4",
    "video_talking_file": "https://media.example.com/avatar/talking.mp4",
}
STATE_WORDS = {"video_idle_file": "idle", "video_listening_file": "listening",
               "video_talking_file": "talking"}


def ai_of(doc):
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def main():
    V.sdk_banner()
    from app import agent

    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    params = ai_of(doc)["params"]
    assert {k: params.get(k) for k in EXPECTED} == EXPECTED, params
    assert {k for k in params if k.startswith("video_")} == set(EXPECTED), sorted(params)

    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    assert ai_of(y)["params"] == EXPECTED, ai_of(y)["params"]
    assert "video call" in ai_of(y)["prompt"]["text"], ai_of(y)["prompt"]
    assert "video call" in json.dumps(ai_of(doc)["prompt"]), ai_of(doc)["prompt"]

    # the schema's word on each key
    props = V.swml_schema()["$defs"]["AIParams"]["properties"]
    for key, word in STATE_WORDS.items():
        desc = props[key]["description"]
        assert word in desc, (key, desc)
        assert "Only works for calls that support video" in desc, (key, desc)
        assert props[key].get("type") == "string", (key, props[key])

    # the schema accepts unknown params, so a misspelt key validates and the
    # documented parameter goes unconfigured: exact keys are the only guard,
    # which is why the assertions above compare them whole
    typo = json.loads(json.dumps(y))
    typo_params = ai_of(typo)["params"]
    typo_params["video_idel_file"] = typo_params.pop("video_idle_file")
    V.validate_swml(typo)
    assert "video_idel_file" not in props, "the schema now knows the misspelt key"

    print(f"ok: ai.params carries idle, listening and talking clips under "
          f"{EXPECTED['video_idle_file'].rsplit('/', 1)[0]}/ on both surfaces; the schema "
          f"documents all three as video-only and accepts a typo, so the keys are pinned")


if __name__ == "__main__":
    main()
