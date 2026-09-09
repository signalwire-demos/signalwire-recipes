"""Prove the claim without a network.

Claim: a call flow is a SWML document the platform hosts, so an IVR needs no
server of yours. One POST creates it from a `title`, a `relayml` document and
its paired `flow_data`, and one POST points a number at it by `phone_route_id`
with the `calling` handler.

Proof: the document validates against the bundled schema and contains answer,
prompt, switch, hangup in order. The prompt collects one digit. The switch
reads `prompt_value`, connects 1 to the sales number and 2 to the workshop
number, and defaults to the fallback. `add_verb` raises on a prompt with no
`play`. With the HTTP layer replaced by a recorder, `deploy` makes one POST to
the documented call flows path with exactly `title` and that document as
`relayml`. `point_number` makes one GET of the phone numbers list filtered to
the number. It then makes one POST to the documented phone routes path with
exactly `phone_route_id` and `handler: calling`. The spec requires `title` on
the flow and both fields on the route. Expected values live here, not in
app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SALES_NUMBER": "+15550100001",
    "WORKSHOP_NUMBER": "+15550100002",
})

import verifylib as V  # noqa: E402

FLOWS = "/api/fabric/resources/call_flows"
NUMBERS = "/api/relay/rest/phone_numbers"
RID = "9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
NID = "1a2b3c4d-0000-4000-8000-000000000001"
MAIN = "+15550001111"
MENU = "say:Thanks for calling Ridgeline Cycles. Press 1 for sales, or 2 for the workshop."


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def body_schema(spec, path):
    op = spec["paths"][path]["post"]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def main():
    V.sdk_banner()
    import app as recipe

    doc = recipe.build().get_document()
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "prompt", "switch", "hangup"], V.verb_names(doc)
    assert V.first(doc, "prompt") == {"play": MENU, "max_digits": 1, "initial_timeout": 8}, V.first(doc, "prompt")
    switch = V.first(doc, "switch")
    assert switch["variable"] == "prompt_value", switch
    assert switch["case"] == {"1": [{"connect": {"to": "+15550100001", "timeout": 25}}],
                              "2": [{"connect": {"to": "+15550100002", "timeout": 25}}]}, switch["case"]
    assert switch["default"] == [{"play": {"url": "say:Sorry, that was not an option. Goodbye."}}], switch

    # add_verb is the schema check: a prompt with no play is refused at build time
    service = recipe.build()
    try:
        service.add_verb("prompt", {"max_digits": 1})
    except Exception as e:  # the SDK's SchemaValidationError
        assert type(e).__name__ == "SchemaValidationError", type(e)
    else:
        raise AssertionError("a prompt without play was accepted")
    assert V.verb_names(service.get_document()) == ["answer", "prompt", "switch", "hangup"]

    rec = V.Recorder(responses=[{"id": RID, "display_name": "Ridgeline Cycles IVR", "type": "call_flow"},
                                {"data": [{"id": "near-miss", "number": MAIN + "9"},
                                          {"id": NID, "number": MAIN}]},
                                {"id": "route-1"}])
    for ns in (recipe.client.fabric.call_flows, recipe.client.fabric.resources,
               recipe.client.phone_numbers):
        ns._http = rec
    flow = recipe.deploy()
    recipe.point_number(flow["id"], MAIN)

    expected = [("POST", FLOWS), ("GET", NUMBERS), ("POST", f"/api/fabric/resources/{RID}/phone_routes")]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    create, lookup, route = rec.calls
    assert create["body"] == {"title": "Ridgeline Cycles IVR", "relayml": doc,
                              "flow_data": {"generated_by": "signalwire-recipes",
                                            "recipe": "build-an-ivr-without-a-server"}}, create["body"]
    assert lookup["params"] == {"filter_number": MAIN}, lookup
    assert route["body"] == {"phone_route_id": NID, "handler": "calling"}, route["body"]

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", FLOWS, create["body"])
    V.assert_documented("rest", "GET", NUMBERS, None, lookup["params"])
    V.assert_documented("rest", "POST", "/api/fabric/resources/{id}/phone_routes", route["body"])
    flow_schema = body_schema(spec, FLOWS)
    assert flow_schema["required"] == ["title"], flow_schema["required"]
    relayml_desc = deref(spec, flow_schema["properties"]["relayml"])["description"]
    assert "SWML document this Call Flow should execute" in relayml_desc
    # the pair rule the first version of this recipe misread: both or neither
    assert "provide both fields together or omit both" in relayml_desc, relayml_desc
    assert "provide both fields together or omit both" in \
        deref(spec, flow_schema["properties"]["flow_data"])["description"]
    route_schema = body_schema(spec, "/api/fabric/resources/{id}/phone_routes")
    assert set(route_schema["required"]) == {"phone_route_id", "handler"}, route_schema["required"]
    # the enum, not the prose: the description says "calls", the enum says calling
    handler_enum = deref(spec, route_schema["properties"]["handler"])["enum"]
    assert handler_enum == ["calling", "messaging"], handler_enum

    # the bundled schema's word on the two verbs the IVR turns on
    defs = V.swml_schema()["$defs"]
    assert defs["Prompt"]["properties"]["prompt"]["required"] == ["play"]
    assert defs["Switch"]["properties"]["switch"]["required"] == ["variable", "case"]

    print(f"ok: the IVR validates (answer, prompt 1 digit, switch on prompt_value to two desks, "
          f"hangup); POST {FLOWS} carries it as relayml; the number {MAIN} is routed with "
          f"handler=calling, and relayml travels with flow_data")


if __name__ == "__main__":
    main()
