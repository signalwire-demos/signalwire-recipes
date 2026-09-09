"""Prove the claim without a network.

Claim: a tool result carries a SWML `user_event` whose `event` is the JSON
object the handler chose. The bundled schema says that verb sends events to
the connected client on the call.

Proof: run the handler with a valid slot and compare the whole result. The
action is a one-verb SWML document, `user_event` with the exact `event`
object, and that document validates against the bundled schema, whose
`user_event` requires `event`. An invalid slot returns a response and no
action. The plain-SWML surface validates and places its event before the `ai`
verb. Expected values live here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# what your .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")

SLOTS = ["fri-10", "sat-09", "thu-14"]
EXPECTED = {
    "response": "Noted Thursday 2pm for the caller.",
    "action": [{"SWML": {"version": "1.0.0", "sections": {"main": [{"user_event": {
        "event": {"type": "slot_selected", "slot": "thu-14", "label": "Thursday 2pm"}}}]}}}],
}


def main():
    V.sdk_banner()
    from app import BookingAgent

    agent = BookingAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["parameters"]["properties"]["slot"]["enum"] == SLOTS, fn

    got = agent._execute_swaig_function("select_slot", {"slot": "thu-14"}, call_id="c1")
    assert got == EXPECTED, json.dumps(got, indent=1)
    inline = got["action"][0]["SWML"]
    V.validate_swml(inline)
    assert V.verb_names(inline) == ["user_event"], V.verb_names(inline)

    # the schema's own rule: user_event needs an event
    bad = {"version": "1.0.0", "sections": {"main": [{"user_event": {}}]}}
    try:
        V.validate_swml(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("a user_event without an event validated")

    got = agent._execute_swaig_function("select_slot", {"slot": "sun-08"}, call_id="c1")
    assert got["response"].startswith("INVALID") and "action" not in got, got

    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    assert V.verb_names(y) == ["answer", "user_event", "ai"], V.verb_names(y)
    assert V.first(y, "user_event")["event"] == {"type": "call_answered", "agent": "booking"}

    # the REST route to the same verb, as the vendored spec documents it
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    variants = [deref(x) for x in schemas["Calling.CallRequest"]["oneOf"]]
    ue = next(x for x in variants
              if "calling.user_event" in (deref(x["properties"]["command"]).get("enum") or []))
    assert set(ue["required"]) == {"command", "id", "params"}, ue.get("required")
    params = deref(ue["properties"]["params"])
    assert params["required"] == ["event"], params.get("required")
    assert deref(params["properties"]["event"])["type"] == "object", params["properties"]

    print(f"ok: select_slot returns one SWML user_event with the exact event object. "
          f"An event-less user_event fails the schema. An unknown slot sends nothing. "
          f"The SWML surface places call_answered before ai. The REST calling.user_event "
          f"variant requires params.event.")


if __name__ == "__main__":
    main()
