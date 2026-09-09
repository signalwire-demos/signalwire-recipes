"""Prove the claim without a network.

Claim: a caller on your blocklist gets a document that is one `hangup` with a
reason and no `answer`, so the call is refused before it is picked up; every
other caller gets `answer` then `connect`. The list is compared by digits, so
formatting does not let a number through.

Proof: the Flask route is driven with payloads shaped like the spec's inbound
call webhook. A blocked number, in a different format from the list, renders
only `hangup` with `decline`; an allowed number and an absent caller id render
`answer` and `connect`; both documents validate against the bundled schema,
whose `hangup.reason` allows exactly `hangup`, `busy` and `decline`. An
unauthenticated request is a 401. The TypeScript surface renders the same
documents and gates the same way. Expected values live here, not in app.py.
"""
import base64
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
USER, PASSWORD = "recipes", "pw"
DESTINATION = "+15550100001"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SWML_BASIC_AUTH_USER": USER,
    "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
    "DESTINATION": DESTINATION,
})

import verifylib as V  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}
BLOCKED_AS_LISTED = "+15555550100"
BLOCKED_REFORMATTED = "1 (555) 555-0101"   # listed as +1 (555) 555-0101
ALLOWED = "+14155550123"
REASONS = ["hangup", "busy", "decline"]


def inbound(caller):
    """The documented inbound-call payload, as far as the handler reads it."""
    call = {"call_id": "c-1", "node_id": "n", "segment_id": "s", "call_state": "created",
            "direction": "inbound", "type": "phone", "to": "+15551230000", "headers": [],
            "project_id": "proj-1234", "space_id": "sp-1"}
    if caller is not None:
        call["from"] = caller
    return {"call": call, "vars": {}, "envs": {}, "params": {}}


def main():
    V.sdk_banner()
    import app as recipe

    # the payload the handler reads is the spec's, key for key
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    hook = spec["webhooks"]["subpackage_callingWebhooks.inbound_call_webhook"]["post"]
    payload_schema = deref(list(hook["requestBody"]["content"].values())[0]["schema"])
    call_schema = deref(payload_schema["properties"]["call"])
    sample = inbound(ALLOWED)
    assert set(call_schema["required"]) <= set(sample["call"]), call_schema["required"]
    assert set(sample["call"]) <= set(call_schema["properties"]), sorted(sample["call"])

    web = recipe.app.test_client()

    def fetch(caller):
        r = web.post("/swml", json=inbound(caller), headers=AUTH)
        assert r.status_code == 200, r.status_code
        doc = r.get_json()
        V.validate_swml(doc)
        return V.verb_names(doc), doc

    # blocked, once as listed and once reformatted: hangup only, no answer
    for caller in (BLOCKED_AS_LISTED, BLOCKED_REFORMATTED):
        names, doc = fetch(caller)
        assert names == ["hangup"], (caller, names)
        assert V.first(doc, "hangup") == {"reason": "decline"}, doc

    # allowed, and no caller id at all: answered and connected
    for caller in (ALLOWED, None):
        names, doc = fetch(caller)
        assert names == ["answer", "connect"], (caller, names)
        assert V.first(doc, "connect") == {"to": DESTINATION}, doc

    # the reason is one the schema allows, and the three it allows are these
    hangup = V.swml_schema()["$defs"]["Hangup"]["properties"]["hangup"]
    allowed = [alt["const"] for alt in hangup["properties"]["reason"]["anyOf"]]
    assert allowed == REASONS, allowed
    assert recipe.REASON in allowed, recipe.REASON

    # the route serves nobody without the credentials
    assert web.post("/swml", json=inbound(ALLOWED)).status_code == 401

    # the TypeScript surface renders the same documents behind the same gate
    node = V.node_surface(HERE, BLOCKED_AS_LISTED, BLOCKED_REFORMATTED, ALLOWED,
                          env={"SWML_BASIC_AUTH_USER": USER,
                               "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                               "DESTINATION": DESTINATION})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        for key in ("blocked", "reformatted"):
            doc = node[key]
            V.validate_swml(doc)
            assert V.verb_names(doc) == ["hangup"], (key, doc)
            assert V.first(doc, "hangup") == {"reason": "decline"}, doc
        for key in ("allowed", "anonymous"):
            doc = node[key]
            V.validate_swml(doc)
            assert V.verb_names(doc) == ["answer", "connect"], (key, doc)
            assert V.first(doc, "connect") == {"to": DESTINATION}, doc
        assert node["unauthorized"] == 401, node
        ts_note = "typescript renders the same four documents and returns the same 401"

    print(f"ok: a listed caller, in either format, gets one hangup with decline and no "
          f"answer; an allowed caller and an absent caller id get answer then connect to "
          f"{DESTINATION}; both documents validate, the reason is in the schema's "
          f"{REASONS}, and an unauthenticated POST is a 401; {ts_note}")


if __name__ == "__main__":
    main()
