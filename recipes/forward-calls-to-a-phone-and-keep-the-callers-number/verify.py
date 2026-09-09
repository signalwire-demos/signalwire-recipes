"""Prove the claim without a network.

Claim: the document forwards the call with `connect`, and its `from` is the
inbound caller's own number, so the phone that rings shows who really called.

Proof: the Flask route is driven with payloads shaped like the spec's inbound
call webhook. For a caller, the one verb is `connect` with `to` the forwarding
target, `from` equal to that caller and the ring timeout; for a request with no
caller id, `from` is absent rather than empty. Both documents validate against
the bundled schema, whose `connect.from` is described as the caller ID to use
when dialing. An unauthenticated request is a 401. The TypeScript surface
renders the same documents behind the same gate. Expected values live here,
not in app.py.
"""
import base64
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
USER, PASSWORD = "recipes", "pw"
FORWARD_TO, RING_FOR = "+15550100001", 25
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SWML_BASIC_AUTH_USER": USER,
    "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
    "FORWARD_TO": FORWARD_TO,
    "RING_FOR": str(RING_FOR),
})

import verifylib as V  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}
CALLER = "+14155550123"


def inbound(caller):
    call = {"call_id": "c-1", "node_id": "n", "segment_id": "s", "call_state": "created",
            "direction": "inbound", "type": "phone", "to": "+15551230000", "headers": [],
            "project_id": "proj-1234", "space_id": "sp-1"}
    if caller is not None:
        call["from"] = caller
    return {"call": call, "vars": {}, "envs": {}, "params": {}}


def main():
    V.sdk_banner()
    import app as recipe

    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    hook = spec["webhooks"]["subpackage_callingWebhooks.inbound_call_webhook"]["post"]
    call_schema = deref(deref(list(hook["requestBody"]["content"].values())[0]["schema"])
                        ["properties"]["call"])
    assert "from" in call_schema["required"], call_schema["required"]
    assert set(call_schema["required"]) <= set(inbound(CALLER)["call"]), call_schema["required"]

    web = recipe.app.test_client()

    def fetch(caller):
        r = web.post("/swml", json=inbound(caller), headers=AUTH)
        assert r.status_code == 200, r.status_code
        doc = r.get_json()
        V.validate_swml(doc)
        assert V.verb_names(doc) == ["connect"], V.verb_names(doc)
        return V.first(doc, "connect")

    # the caller's number rides along as the caller ID
    assert fetch(CALLER) == {"to": FORWARD_TO, "timeout": RING_FOR, "from": CALLER}
    # no caller id: the key is absent, not empty
    assert fetch(None) == {"to": FORWARD_TO, "timeout": RING_FOR}

    # the schema says what from is for
    connect = V.swml_schema()["$defs"]["ConnectDeviceSingle"]["properties"]
    assert connect["from"]["description"] == "The caller ID to use when dialing the number."
    assert connect["timeout"]["default"] == 60

    assert web.post("/swml", json=inbound(CALLER)).status_code == 401

    node = V.node_surface(HERE, CALLER, env={"SWML_BASIC_AUTH_USER": USER,
                                              "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                                              "FORWARD_TO": FORWARD_TO,
                                              "RING_FOR": str(RING_FOR)})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        for key, want in (("withCaller", {"to": FORWARD_TO, "timeout": RING_FOR, "from": CALLER}),
                          ("anonymous", {"to": FORWARD_TO, "timeout": RING_FOR})):
            V.validate_swml(node[key])
            assert V.verb_names(node[key]) == ["connect"], node[key]
            assert V.first(node[key], "connect") == want, (key, node[key])
        assert node["unauthorized"] == 401, node
        ts_note = "typescript renders the same two documents and returns the same 401"

    print(f"ok: a call from {CALLER} renders one connect to {FORWARD_TO} with from "
          f"{CALLER} and timeout {RING_FOR}; no caller id leaves from out; both validate, "
          f"the schema calls from the caller ID to use when dialing, and an "
          f"unauthenticated POST is a 401; {ts_note}")


if __name__ == "__main__":
    main()
