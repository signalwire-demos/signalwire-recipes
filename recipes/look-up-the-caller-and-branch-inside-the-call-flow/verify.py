"""Prove the claim without a network.

Claim: a hosted call flow fetches the caller's record with `request`, branches
on a field of the parsed response with `switch`, and falls back to a human with
`cond` when the lookup fails. No server of yours is in the call path.

Proof: the document validates and its four verbs are in order. The `request`
carries the caller's number by substitution, `save_variables` true and both
timeouts; the `cond` holds a `when` on `request_result` whose `then` is the
`switch` on `request_response.tier`, and an `else` that plays a line and still
connects. `add_verb` refuses the list-shaped `cond`, which is why it is
appended, and it refuses a `request` with no `url`. Three documented requests
deploy the flow and bind a number. The TypeScript surface builds the same
document and sends the same requests. Expected values live here.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
GOLD, STANDARD = "+15550100001", "+15550100002"
CRM_URL = "https://crm.example.test/lookup"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com", "CRM_URL": CRM_URL,
    "CRM_TOKEN": "crm-token", "GOLD_NUMBER": GOLD, "STANDARD_NUMBER": STANDARD,
})

import verifylib as V  # noqa: E402

FLOWS = "/api/fabric/resources/call_flows"
NUMBERS = "/api/relay/rest/phone_numbers"
RID, NID, MAIN = "flow-abc", "pn-111", "+15551230000"
APOLOGY = "One moment, I could not look up your account."
GOLD_LEG = {"connect": {"to": GOLD, "timeout": 25}}
STANDARD_LEG = {"connect": {"to": STANDARD, "timeout": 25}}
EXPECTED_REQUEST = {
    "url": CRM_URL, "method": "POST",
    "headers": {"Content-Type": "application/json", "Authorization": "Bearer crm-token"},
    "body": {"phone": "%{call.from}"}, "save_variables": True,
    "connect_timeout": 3, "timeout": 5,
}
EXPECTED_COND = [
    {"when": "request_result == 'success'",
     "then": [{"switch": {"variable": "request_response.tier",
                          "case": {"gold": [GOLD_LEG], "standard": [STANDARD_LEG]},
                          "default": [STANDARD_LEG]}}]},
    {"else": [{"play": {"url": f"say:{APOLOGY}"}}, STANDARD_LEG]},
]
FLOW_DATA = {"generated_by": "signalwire-recipes",
             "recipe": "look-up-the-caller-and-branch-inside-the-call-flow"}


def check_document(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "request", "cond", "hangup"], \
        (label, V.verb_names(doc))
    assert V.first(doc, "request") == EXPECTED_REQUEST, (label, V.first(doc, "request"))
    cond = V.first(doc, "cond")
    assert cond == EXPECTED_COND, (label, json.dumps(cond))


def main():
    V.sdk_banner()
    import app as recipe

    doc = recipe.build().get_document()
    check_document(doc, "python")

    # the schema is what each verb is checked against as it is added
    defs = V.swml_schema()["$defs"]
    req = defs["Request"]["properties"]["request"]
    assert req["required"] == ["url", "method"], req["required"]
    assert "Store parsed JSON response as variables" in \
        req["properties"]["save_variables"]["description"]
    assert req["properties"]["timeout"]["default"] == 0, req["properties"]["timeout"]
    assert req["properties"]["connect_timeout"]["default"] == 0
    assert defs["CondReg"]["required"] == ["when", "then"], defs["CondReg"]["required"]
    assert defs["CondElse"]["required"] == ["else"], defs["CondElse"]["required"]
    assert defs["Switch"]["properties"]["switch"]["required"] == ["variable", "case"]
    # both prefixes are the same variable syntax
    assert defs["SWMLVar"]["pattern"] == r"^[\$%]\{.*\}$", defs["SWMLVar"]

    # add_verb takes a dict, so the list-shaped cond cannot go through it
    service = recipe.build()
    assert service.add_verb("cond", EXPECTED_COND) is False
    # and it refuses a request that the schema would reject
    try:
        service.add_verb("request", {"method": "POST"})
    except Exception as e:                       # the SDK's SchemaValidationError
        assert type(e).__name__ == "SchemaValidationError", type(e)
    else:
        raise AssertionError("a request with no url was accepted")
    assert V.verb_names(service.get_document()) == ["answer", "request", "cond", "hangup"]

    # deploy and bind, as three documented requests
    rec = V.Recorder(responses=[{"id": RID, "type": "call_flow"},
                                {"data": [{"id": "near-miss", "number": MAIN + "9"},
                                          {"id": NID, "number": MAIN}]},
                                {"id": "route-1"}])
    V.record_everything(recipe.client, rec)
    flow = recipe.deploy()
    recipe.point_number(flow["id"], MAIN)

    bind = f"/api/fabric/resources/{RID}/phone_routes"
    got = [(c["method"], c["path"]) for c in rec.calls]
    assert got == [("POST", FLOWS), ("GET", NUMBERS), ("POST", bind)], got
    create, lookup, route = rec.calls
    assert create["body"] == {"title": "Ridgeline Cycles router", "relayml": doc,
                              "flow_data": FLOW_DATA}, create["body"]
    assert lookup["params"] == {"filter_number": MAIN}, lookup
    assert route["body"] == {"phone_route_id": NID, "handler": "calling"}, route["body"]
    V.assert_documented("rest", "POST", FLOWS, create["body"])
    V.assert_documented("rest", "GET", NUMBERS, None, lookup["params"])
    V.assert_documented("rest", "POST", bind, route["body"])

    node = V.node_surface(HERE, RID, MAIN, NID)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        check_document(node["doc"], "typescript")
        tgot = [(c["method"], c["path"], c["body"]) for c in node["captured"]]
        assert tgot == [("POST", FLOWS, create["body"]), ("GET", NUMBERS, None),
                        ("POST", bind, route["body"])], tgot
        ts_note = "typescript builds the same document and sends the same three requests"

    print(f"ok: answer, request to {CRM_URL} with save_variables true, then a cond whose "
          f"when branches on request_result and whose then switches on "
          f"request_response.tier to {GOLD} or {STANDARD}, and whose else still connects "
          f"after an apology; add_verb refuses the list-shaped cond and a request "
          f"with no url; the flow is created with relayml and flow_data and bound "
          f"to {MAIN}; "
          f"{ts_note}")


if __name__ == "__main__":
    main()
