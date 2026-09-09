"""Prove the claim without a network.

Claim: callers wait in a named queue with hold audio and are bridged in order
as agents connect to it.

Proof: the caller, wait and agent documents validate against the SWML schema;
the caller enters the named queue with a wait_url and a bounded wait_time and
has a fall-through after it; the agent document connects to "queue:<name>";
the YAML surface carries the same three sections.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("PUBLIC_URL", "https://recipes.example.test")

import verifylib as V  # noqa: E402


def check_caller(doc, section="main"):
    names = V.verb_names(doc, section)
    i = names.index("enter_queue")
    assert names[i + 1:] == ["play", "hangup"], names  # fall-through when nobody answers
    q = V.first(doc, "enter_queue", section)
    assert q["queue_name"] == "support", q
    assert q["wait_url"].endswith("/wait"), q
    assert 0 < q["wait_time"] <= 3600, q
    return q


def main():
    V.sdk_banner()
    import app as recipe
    caller, wait, agent = (b().get_document() for b in
                           (recipe.build_caller, recipe.build_wait, recipe.build_agent))
    for d in (caller, wait, agent):
        V.validate_swml(d)
    q = check_caller(caller)
    assert q["wait_url"] == "https://recipes.example.test/wait", q
    assert V.verb_names(wait) == ["play"], V.verb_names(wait)
    assert V.first(agent, "connect")["to"] == "queue:support", agent

    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    assert set(y["sections"]) == {"main", "wait", "agent"}, set(y["sections"])
    check_caller(y)
    assert V.first(y, "connect", "agent")["to"] == "queue:support"

    c = recipe.app.test_client()
    for route, verb in (("/caller", "enter_queue"), ("/wait", "play"), ("/agent", "connect")):
        assert verb in V.verb_names(c.get(route).get_json()), route
    print("ok: enter_queue(support, wait_url, wait_time) + fall-through; agent connects to queue:support")
    return 0


if __name__ == "__main__":
    sys.exit(main())
