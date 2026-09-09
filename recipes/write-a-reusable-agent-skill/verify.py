"""Prove the claim without a network.

Claim: a SkillBase subclass packages tools, hints and prompt sections so any
agent can add_skill it with params.

Proof: registering the class makes it addressable by name, and one add_skill
line puts all three of its contributions into the rendered SWML. Adding it
twice with different params yields two instances, which only works because the
instance key is built from tool_name; without a distinct one only one tool
survives, which is what this asserts.
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


def ai_of(agent):
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def main():
    V.sdk_banner()
    from signalwire.skills import skill_registry
    from skill import DEFAULT_HOURS, StoreHoursSkill
    import app as recipe

    # The class is addressable by the name it declares.
    assert skill_registry.get_skill_class("store_hours") is StoreHoursSkill
    assert StoreHoursSkill.SKILL_NAME == "store_hours"

    agent = recipe.ShopAgent()
    V.assert_basic_auth_from_env(agent)
    ai = ai_of(agent)

    # 1. Tools. Two instances of one class, each with its own tool.
    tools = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert set(tools) == {"shop_hours", "workshop_hours"}, sorted(tools)
    for name, fn in tools.items():
        assert fn["parameters"]["required"] == ["day"], fn
        assert fn["parameters"]["properties"]["day"]["description"], fn
    # each description names its own location, so the model can tell them apart
    assert "the shop" in tools["shop_hours"]["description"], tools["shop_hours"]
    assert "the workshop" in tools["workshop_hours"]["description"], tools

    # 2. Hints, contributed by the skill rather than the agent.
    hints = ai["hints"]
    assert "the shop" in hints and "the workshop" in hints, hints
    assert "opening hours" in hints, hints

    # 3. Prompt sections, also from the skill. Each must name the tool its
    # own instance registered: naming the skill would point the model at a
    # tool that does not exist once tool_name differs.
    pom = json.dumps(ai["prompt"])
    assert "Hours for the shop" in pom, ai["prompt"]
    assert "Hours for the workshop" in pom, ai["prompt"]
    assert "Never guess an opening time" in pom, ai["prompt"]
    for tool in tools:
        assert f"Use {tool} to answer" in pom, (tool, ai["prompt"])
    assert "Use store_hours to answer" not in pom, ai["prompt"]

    # params really do reach the handler: different hours per instance.
    r = agent._execute_swaig_function("shop_hours", {"day": "saturday"},
                                      call_id="c1")
    assert DEFAULT_HOURS["saturday"] in r["response"], r
    r = agent._execute_swaig_function("workshop_hours", {"day": "saturday"},
                                      call_id="c1")
    assert "closed" in r["response"], r

    # a bad day is a typed refusal, not an invented time
    r = agent._execute_swaig_function("shop_hours", {"day": "someday"},
                                      call_id="c1")
    assert r["response"].startswith("UNKNOWN_DAY"), r
    for hours in DEFAULT_HOURS.values():
        assert hours == "closed" or hours not in r["response"], r

    # The instance key is tool_name, so omitting it drops the second silently.
    class OneAgent(recipe.AgentBase):
        def __init__(self):
            super().__init__(name="one", route="/one")
            self.add_skill("store_hours", {"location": "a"})
            self.add_skill("store_hours", {"location": "b"})

    only = [f["function"] for f in ai_of(OneAgent())["SWAIG"]["functions"]]
    assert only == ["store_hours"], only

    print(f"ok: one class registered by name gives {sorted(tools)} plus its "
          f"own hints and prompt sections; without a distinct tool_name the "
          f"second instance collapses to {only}")


if __name__ == "__main__":
    main()
