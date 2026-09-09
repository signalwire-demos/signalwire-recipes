"""Prove the claim without a network.

Claim: the agent collects, confirms, and then commits once through a single
tool. The confirmation is an answer the handler judges against an allow-list
of whole phrases, and nothing is written before a yes the code accepted.

Proof: run the handlers in the platform's payload shape, threading
`global_data` the way the platform does, and assert the order book after each
step. Committing before any order, and before confirmation, refuses and writes
nothing. "Yesterday", "no", "I can't say yes", "sure thing" and an empty
answer are not a yes. "Yes, that's right." is, with the readback in the
response, and so is "Yes, thank you!" once politeness is dropped.
Changing the order after confirming resets the confirmation. Committing after
confirmation writes once and returns an order id; committing again on the same
call refuses with the same id and the book still holds one order. A different
call id gets its own order. An empty or all-unknown item list is refused with
no action. Expected values live here, not in app.py.
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

# Expected values live here, not imported from app.py.
CATALOGUE = ["cargo-rack", "helmet", "puncture-kit"]
TOOLS = ["commit_order", "confirm_order", "set_order"]


class Session:
    """Threads global_data between tool calls the way the platform does."""

    def __init__(self, agent, call_id):
        self.agent, self.call_id, self.data = agent, call_id, {}

    def run(self, tool, **args):
        raw = {"call_id": self.call_id, "global_data": dict(self.data)}
        r = self.agent._execute_swaig_function(tool, args, call_id=self.call_id,
                                               raw_data=raw)
        for action in r.get("action", []):
            if "set_global_data" in action:
                self.data.update(action["set_global_data"])
        return r


def main():
    V.sdk_banner()
    import app as recipe

    agent = recipe.agent
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fns = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert sorted(fns) == TOOLS, sorted(fns)
    enum = fns["set_order"]["parameters"]["properties"]["items"]["items"]["enum"]
    assert enum == CATALOGUE, enum

    book = recipe.ORDERS
    book.clear()
    s = Session(agent, "call-A")

    # commit with nothing on record: refused, nothing written
    r = s.run("commit_order")
    assert r["response"].startswith("INCOMPLETE") and "action" not in r, r
    assert book == {}

    # confirm with no order: refused
    r = s.run("confirm_order", answer="yes")
    assert r["response"].startswith("INCOMPLETE") and "action" not in r, r

    # nothing usable: refused, session and book untouched
    for items in ([], ["unicycle"]):
        r = s.run("set_order", items=items)
        assert r["response"].startswith("INVALID") and "action" not in r, r
        assert s.data == {} and book == {}

    # the order, with one item that is not in the catalogue dropped
    r = s.run("set_order", items=["helmet", "puncture-kit", "unicycle"])
    assert r["action"] == [{"set_global_data": {
        "order": {"items": ["helmet", "puncture-kit"], "total": 101.5},
        "confirmed": False}}], r
    assert book == {}

    # commit before confirmation: refused, nothing written
    r = s.run("commit_order")
    assert r["response"].startswith("NOT_CONFIRMED") and "action" not in r, r
    assert book == {}

    # answers the handler does not accept as a yes: nothing changes
    for answer in ("yesterday", "no", "I can't say yes", "", "yes or no", "sure thing"):
        r = s.run("confirm_order", answer=answer)
        assert r["response"].startswith("NOT_A_YES") and "action" not in r, (answer, r)
        assert s.data["confirmed"] is False
    r = s.run("commit_order")
    assert r["response"].startswith("NOT_CONFIRMED") and book == {}, r

    # a yes, with the readback in the response; then change the order and the
    # confirmation is gone again
    r = s.run("confirm_order", answer="Yes, that's right.")
    assert r == {"response": "Confirmed: helmet, puncture-kit for 101.50. You may "
                             "commit it now.",
                 "action": [{"set_global_data": {"confirmed": True}}]}, r
    s.run("set_order", items=["cargo-rack"])
    assert s.data["confirmed"] is False, s.data
    r = s.run("commit_order")
    assert r["response"].startswith("NOT_CONFIRMED"), r
    assert book == {}

    # confirm and commit: one write, one id. Politeness and punctuation are
    # dropped before the lookup, so this is the whole answer "yes"
    r = s.run("confirm_order", answer="Yes, thank you!")
    assert s.data["confirmed"] is True, r
    r = s.run("commit_order")
    assert r["action"] == [{"set_global_data": {"order_id": "RC-1001"}}], r
    assert book == {"call-A": {"id": "RC-1001", "items": ["cargo-rack"], "total": 45.0}}

    # the model asks again: refused with the same id, still one order
    r = s.run("commit_order")
    assert r["response"].startswith("ALREADY_PLACED") and "RC-1001" in r["response"], r
    assert "action" not in r and len(book) == 1

    # another call is its own transaction
    t = Session(agent, "call-B")
    t.run("set_order", items=["helmet"])
    t.run("confirm_order", answer="correct")
    r = t.run("commit_order")
    assert r["action"] == [{"set_global_data": {"order_id": "RC-1002"}}], r
    assert sorted(book) == ["call-A", "call-B"]

    print(f"ok: {TOOLS} with the catalogue enum {CATALOGUE}; commit refused before "
          f"an order and before a yes; yesterday/no/I can't say yes are not a yes; "
          f"a changed order drops the confirmation; one commit per call id, a "
          f"repeat returns the same id; the book holds {len(book)} orders")


if __name__ == "__main__":
    main()
