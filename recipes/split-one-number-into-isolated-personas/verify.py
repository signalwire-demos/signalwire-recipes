"""Prove the claim without a network.

Claim: the default context's step lists sales, support and billing in
`valid_contexts` and names no tools. Each persona is an isolated context, and
its step offers the model only that desk's tool. The three tools are stubs with
fixed replies.

Proof: render the document and read `ai.prompt.contexts`. The default context's
step names no functions and lists exactly the three personas in
`valid_contexts`. Each persona context carries `isolated: true`, its own
prompt, and one step whose `functions` is exactly its one tool, with
`valid_contexts` back to default. No persona step names another persona's tool. The three tools all
exist on the agent, so the steps are what scopes them. The bundled schema
documents `isolated` on a context. Expected values live here, not in app.py.
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

PERSONAS = {"sales": "quote_price", "support": "book_repair", "billing": "look_up_invoice"}


def main():
    V.sdk_banner()
    from app import agent  # the module-level agent app.py serves

    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    contexts = ai["prompt"]["contexts"]
    assert sorted(contexts) == sorted(["default", *PERSONAS]), sorted(contexts)

    # the default context: no tools, and only the three personas as destinations
    (ask,) = contexts["default"]["steps"]
    assert ask["functions"] == [], ask.get("functions")
    assert sorted(ask["valid_contexts"]) == sorted(PERSONAS), ask.get("valid_contexts")
    assert "isolated" not in contexts["default"], contexts["default"]

    # each persona: isolated, its own prompt, exactly its own tool
    for name, tool in PERSONAS.items():
        ctx = contexts[name]
        assert ctx["isolated"] is True, (name, ctx.get("isolated"))
        assert any(s["title"] == "Role" and name in s["body"].lower()
                   for s in ctx["pom"]), (name, ctx.get("pom"))
        (step,) = ctx["steps"]
        # the other desks' tools first, so this can fail on its own
        others = set(PERSONAS.values()) - {tool}
        assert not others & set(step["functions"]), (name, step["functions"])
        assert step["functions"] == [tool], (name, step.get("functions"))
        assert step["valid_contexts"] == ["default"], (name, step.get("valid_contexts"))
        assert step["end"] is True, (name, step)

    # all three tools exist on the agent: the step, not the registry, scopes them
    names = sorted(f["function"] for f in ai["SWAIG"]["functions"])
    assert names == sorted(PERSONAS.values()), names

    # the stubs answer with fixed text and no action
    for tool, args, reply in [("quote_price", {"item": "helmet"}, "helmet is 89.00."),
                              ("book_repair", {"day": "Thursday"}, "Booked for Thursday."),
                              ("look_up_invoice", {"number": "1042"},
                               "Invoice 1042: 45.00, paid.")]:
        r = agent._execute_swaig_function(tool, args, call_id="c1")
        assert r == {"response": reply}, (tool, r)

    # the schema's own field
    field = V.swml_schema()["$defs"]["ContextsPOMObject"]["properties"]["isolated"]
    assert field["type"] == "boolean", field
    assert "resets conversation history to only the system prompt" in field["description"]

    print(f"ok: the default context offers {sorted(PERSONAS)} and no tools; each persona is "
          f"isolated with exactly its own tool; all three tools live on the agent")


if __name__ == "__main__":
    main()
