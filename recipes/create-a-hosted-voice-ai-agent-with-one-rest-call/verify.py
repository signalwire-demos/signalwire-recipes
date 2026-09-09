"""Prove the claim without a network.

Claim: the `ai` verb an `AgentBase` renders is what `POST
/api/fabric/resources/ai_agents` takes, so one POST turns your agent definition
into a resource SignalWire hosts, and one more POST puts a number on it.

Proof: the agent is rendered offline and its `prompt`, `params` and
`post_prompt` become the request body. That body is checked against the spec:
`name` and `prompt` are its required fields and every key sent is documented.
The same three objects, wrapped back into an `ai` verb, validate against the
bundled SWML schema, which is the reference the spec points at for each field.
The phone route is exactly `phone_route_id` plus `handler: calling`, and the
number id comes from an exact match after a contains-match lookup, proven with
a fixture of two numbers. The TypeScript surface renders the same agent and is
held to the same bodies. Expected values live here, not in app.py.
"""
import json
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
    "SWML_BASIC_AUTH_USER": "u",
    "SWML_BASIC_AUTH_PASSWORD": "p",
})

import verifylib as V  # noqa: E402

AGENTS = "/api/fabric/resources/ai_agents"
NUMBERS = "/api/relay/rest/phone_numbers"
NAME = "ridgeline-front-desk"
AGENT_ID = "0b7a2f3e-9c41-4d6e-8a52-1f0e3d2c4b5a"
MAIN, NEAR = "+15551230000", "+15551230001"
NID, NEAR_ID = "num-main", "num-near"
SECTIONS = ["Role", "Hours", "Limits"]
POST_PROMPT = "Summarise the call in one sentence."
PARAMS = {"end_of_speech_timeout": 700}


def body_schema(spec, path, method="post"):
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    op = spec["paths"][path][method]
    return deref(list(op["requestBody"]["content"].values())[0]["schema"]), deref


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[
        {"id": AGENT_ID, "display_name": NAME, "type": "ai_agent",
         "ai_agent": {"name": NAME, "agent_id": AGENT_ID}},
        # a contains-match returns the neighbour too; the recipe must pick MAIN
        {"data": [{"id": NEAR_ID, "number": NEAR}, {"id": NID, "number": MAIN}]},
        {"id": AGENT_ID, "type": "ai_agent"},
    ])
    V.record_everything(recipe.client, rec)

    # the body is the rendered agent, not a hand-written copy of it
    body = recipe.definition()
    assert body["name"] == NAME
    assert [s["title"] for s in body["prompt"]["pom"]] == SECTIONS, body["prompt"]
    assert body["post_prompt"] == {"text": POST_PROMPT}, body["post_prompt"]
    assert body["params"] == PARAMS, body["params"]

    made = recipe.create()
    assert made["id"] == AGENT_ID
    recipe.point_number(AGENT_ID, MAIN)

    sent = [(c["method"], c["path"]) for c in rec.calls]
    assert sent == [("POST", AGENTS), ("GET", NUMBERS),
                    ("POST", f"/api/fabric/resources/{AGENT_ID}/phone_routes")], sent

    # the create: required fields present, every key documented, and the
    # prompt object is the SWML ai.prompt the spec points at
    spec = V.spec("rest")
    create = rec.calls[0]["body"]
    assert create == body, create
    V.assert_documented("rest", "POST", AGENTS, create)
    schema, deref = body_schema(spec, AGENTS)
    assert set(schema["required"]) == {"prompt", "name"}, schema["required"]
    for key in ("prompt", "params", "post_prompt"):
        said = " ".join(deref(schema["properties"][key]).get("description", "").split())
        assert "SWML reference" in said, (key, said)
    V.validate_swml({"version": "1.0.0", "sections": {"main": [{"ai": {
        "prompt": create["prompt"], "params": create["params"],
        "post_prompt": create["post_prompt"]}}]}})

    # the lookup, the exact match, and the route
    lookup = rec.calls[1]
    assert lookup["params"] == {"filter_number": MAIN}, lookup
    route = rec.calls[2]["body"]
    assert route == {"phone_route_id": NID, "handler": "calling"}, route
    V.assert_documented("rest", "POST", "/api/fabric/resources/{id}/phone_routes", route)
    route_schema, deref = body_schema(spec, "/api/fabric/resources/{id}/phone_routes")
    assert deref(route_schema["properties"]["handler"])["enum"] == ["calling", "messaging"]

    # a number that is not in the project is refused before any route is posted
    rec2 = V.Recorder(responses=[{"data": [{"id": NEAR_ID, "number": NEAR}]}])
    V.record_everything(recipe.client, rec2)
    try:
        recipe.point_number(AGENT_ID, MAIN)
    except LookupError as exc:
        assert MAIN in str(exc), exc
    else:
        raise AssertionError("routed a number the project does not hold")
    assert [c["method"] for c in rec2.calls] == ["GET"], rec2.calls

    # the TypeScript surface renders its own agent and sends the same requests
    node = V.node_surface(HERE, AGENT_ID, MAIN, NEAR, NID, NEAR_ID)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert [(c["method"], c["path"]) for c in node["captured"]] == sent, node
        ts_create = node["captured"][0]["body"]
        assert ts_create["name"] == NAME
        # 2.0.5 renders the sections as markdown text where 3.0.1 renders a pom
        # list; ai.prompt allows both, and the same three sections are there
        text = ts_create["prompt"]["text"]
        assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == SECTIONS
        for section in create["prompt"]["pom"]:
            assert section["body"] in text, section["title"]
        assert ts_create["post_prompt"] == {"text": POST_PROMPT}, ts_create
        assert ts_create["params"] == PARAMS, ts_create
        assert set(ts_create) == set(create), (set(ts_create), set(create))
        V.validate_swml({"version": "1.0.0", "sections": {"main": [{"ai": {
            "prompt": ts_create["prompt"], "params": ts_create["params"],
            "post_prompt": ts_create["post_prompt"]}}]}})
        assert node["captured"][2]["body"] == route, node["captured"][2]
        assert node["refused"] is True, node
        ts_note = ("typescript renders the same sections as prompt text rather than a "
                   "pom, the same params and post_prompt, sends the same three requests, "
                   "and refuses the same number")

    print(f"ok: the rendered ai verb becomes POST {AGENTS} with the spec's required "
          f"name and prompt, the same objects validate as SWML, GET {NUMBERS} with "
          f"filter_number picks {MAIN} over its neighbour, and the phone route is "
          f"phone_route_id plus handler calling; a number not in the project is "
          f"refused before any route; {ts_note}")


if __name__ == "__main__":
    main()
