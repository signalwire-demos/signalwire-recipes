"""Prove the claim without a network.

Claim: a function with a JSON-schema signature becomes something the model can
call mid-call, and your code decides what it gets back.

Proof: the rendered SWML carries the function in ai.SWAIG.functions with the
exact parameter schema, its LLM-facing descriptions and its fillers; running the
handler returns a spoken answer for a known order and a typed NOT_FOUND state
for an unknown one, with no invented delivery date. The TypeScript surface
renders the same function definition, and its own /swaig route, posted the
documented `argument: {parsed, raw}` shape, returns the same two sentences and
refuses a request without credentials. Expected values live here.
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

KNOWN, UNKNOWN = "48815", "00000"
KNOWN_SAID = "Order 48815 is out for delivery, arriving today before 8pm with Britewave."
NOT_FOUND = ("NOT_FOUND: no order 00000. Ask the caller to read the five digit order "
             "number back, then try again.")


def main():
    V.sdk_banner()
    from app import ORDERS, OrderAgent

    agent = OrderAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]

    # The tool reaches the platform under the key it will be called by.
    funcs = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert "get_order_status" in funcs, list(funcs)
    fn = funcs["get_order_status"]

    # The JSON schema is what the model fills in.
    params = fn["parameters"]
    assert params["type"] == "object", params
    assert list(params["properties"]) == ["order_id"], params
    assert params["required"] == ["order_id"], params

    # Descriptions are LLM-facing: an undescribed parameter is the #1 cause
    # of a tool that exists but never gets called.
    assert len(fn["description"]) > 40, fn["description"]
    assert params["properties"]["order_id"]["description"], params

    # Fillers cover the latency of the lookup.
    assert fn["fillers"]["en-US"], fn

    # A known order: the handler formats for speech, the prompt does not.
    r = agent._execute_swaig_function(
        "get_order_status", {"order_id": KNOWN}, call_id="c1")
    assert r["response"] == KNOWN_SAID, r

    # An unknown order: a typed state that tells the model what to do, and
    # no date anywhere in the reply for it to read out.
    r = agent._execute_swaig_function(
        "get_order_status", {"order_id": UNKNOWN}, call_id="c1")
    miss = r["response"]
    assert miss == NOT_FOUND, miss
    for order in ORDERS.values():
        assert order["eta"] not in miss, miss

    # the TypeScript surface: same definition, same two sentences, through its
    # own route and the documented argument shape
    node = V.node_surface(HERE, KNOWN, UNKNOWN,
                          env={"SWML_BASIC_AUTH_USER": USER,
                               "SWML_BASIC_AUTH_PASSWORD": PASSWORD})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        V.validate_swml(node["doc"])
        (ts_fn,) = node["functions"]["functions"]
        for key in ("function", "description", "parameters", "fillers"):
            assert ts_fn[key] == fn[key], (key, ts_fn[key], fn[key])
        assert node["known"] == {"status": 200, "json": {"response": KNOWN_SAID}}, node
        assert node["unknown"]["json"]["response"] == NOT_FOUND, node["unknown"]
        assert node["unauthorized"] == 401, node
        ts_note = ("typescript renders the same definition and its /swaig route "
                   "returns the same two sentences, 401 without credentials")

    print(f"ok: get_order_status exposed with {list(params['properties'])} "
          f"(required {params['required']}); known order answered, "
          f"unknown order returns {miss.split(':')[0]}; {ts_note}")


if __name__ == "__main__":
    main()
