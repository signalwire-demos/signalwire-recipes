"""Prove the claim without a network.

Claim: a subscriber is a Fabric resource with an address of its own, and a
subscriber token is what a browser registers with. A SWML `connect` to that
address is the document that rings the registered browser.

Proof: with the HTTP layer replaced by a recorder, `create_subscriber` makes
one POST to the documented subscribers path with exactly `email` and
`display_name`, then one GET of the resource's addresses, and returns the
address name. `browser_token` makes one POST to the documented subscriber
tokens path with exactly `reference`. The spec requires `email` on the
subscriber and `reference` on the token, documents `token` and
`refresh_token` in the response, and documents `name` and `channels` on an
address. The document validates, contains answer, play, connect, hangup, and
its `connect.to` is the address; the bundled schema lists a Call Fabric
Resource address among the forms `connect.to` takes. A subscriber that lists
no address fails with a message. Expected values live here, not in app.py.
"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SUBSCRIBER_EMAIL": "dana@ridgeline.example",
    "SUBSCRIBER_NAME": "Dana at the workshop",
})

import verifylib as V  # noqa: E402

SUBSCRIBERS = "/api/fabric/resources/subscribers"
TOKENS = "/api/fabric/subscribers/tokens"
RID = "6a7b8c9d-0e1f-4a2b-8c3d-4e5f6a7b8c9d"
ADDRESS = "/private/dana"


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def body_schema(spec, path):
    op = spec["paths"][path]["post"]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def response_props(spec, path, method):
    op = spec["paths"][path][method]
    code = next(c for c in op["responses"] if c.startswith("2"))
    schema = deref(spec, op["responses"][code]["content"]["application/json"]["schema"])
    if "data" in schema.get("properties", {}):
        schema = deref(spec, deref(spec, schema["properties"]["data"]).get("items"))
    return code, schema.get("properties", {})


def main():
    V.sdk_banner()
    import app as recipe

    address_item = {"id": "addr-1", "name": ADDRESS, "display_name": "Dana at the workshop",
                    "type": "subscriber", "channels": {"audio": f"{ADDRESS}?channel=audio",
                                                       "video": f"{ADDRESS}?channel=video"}}
    rec = V.Recorder(responses=[
        {"id": RID, "display_name": "Dana at the workshop", "type": "subscriber",
         "subscriber": {"id": "sub-1", "email": "dana@ridgeline.example"}},
        {"data": [address_item]},
        {"subscriber_id": "sub-1", "token": "sat-verifier-only", "refresh_token": "rt-verifier-only"},
    ])
    recipe.client.fabric.subscribers._http = rec
    recipe.client.fabric.tokens._http = rec

    resource_id, address = recipe.create_subscriber()
    assert (resource_id, address) == (RID, ADDRESS), (resource_id, address)
    minted = recipe.browser_token()
    assert minted["token"] == "sat-verifier-only" and minted["refresh_token"] == "rt-verifier-only", minted

    expected = [("POST", SUBSCRIBERS), ("GET", f"{SUBSCRIBERS}/{RID}/addresses"), ("POST", TOKENS)]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    create, listing, token = rec.calls
    assert create["body"] == {"email": "dana@ridgeline.example",
                              "display_name": "Dana at the workshop"}, create["body"]
    assert listing["body"] is None and listing["params"] is None, listing
    assert token["body"] == {"reference": "dana@ridgeline.example"}, token["body"]

    # a subscriber with no address yet fails with a message, not an IndexError
    rec2 = V.Recorder(responses=[{"id": "r-2"}, {"data": []}])
    recipe.client.fabric.subscribers._http = rec2
    try:
        recipe.create_subscriber()
    except RuntimeError as e:
        assert "r-2" in str(e), str(e)
    else:
        raise AssertionError("an address-less subscriber did not fail")

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", SUBSCRIBERS, create["body"])
    V.assert_documented("rest", "GET", "/api/fabric/resources/{id}/addresses", None)
    V.assert_documented("rest", "POST", TOKENS, token["body"])
    assert body_schema(spec, SUBSCRIBERS)["required"] == ["email"]
    tok = body_schema(spec, TOKENS)
    assert tok["required"] == ["reference"], tok["required"]
    assert "uniquely identifies the subscriber" in deref(spec, tok["properties"]["reference"])["description"]
    code, props = response_props(spec, TOKENS, "post")
    assert code == "200" and {"subscriber_id", "token", "refresh_token"} <= set(props), (code, sorted(props))
    code, props = response_props(spec, "/api/fabric/resources/{id}/addresses", "get")
    assert {"id", "name", "channels"} <= set(props), sorted(props)
    assert set(address_item) <= set(props), sorted(set(address_item) - set(props))

    # the document that rings the browser
    doc = recipe.ring(address).get_document()
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "play", "connect", "hangup"], V.verb_names(doc)
    assert V.first(doc, "connect") == {"to": ADDRESS, "timeout": 30}, V.first(doc, "connect")
    to_desc = V.swml_schema()["$defs"]["ConnectDeviceSingle"]["properties"]["to"]["description"]
    assert "Call Fabric Resource address" in to_desc, to_desc

    # the browser side registers and answers; the first version pointed at a
    # client that only dials (codex, wave 10 review)
    ts = (HERE / "typescript" / "index.ts").read_text(encoding="utf-8")
    for needle in ("SignalWire({ token })", "client.online(", "incomingCallHandlers",
                   ".accept({ rootElement", ".reject()"):
        assert needle in ts, f"typescript client lacks {needle}"
    compiled = V.type_check_typescript(HERE, "@signalwire/js")

    print(f"ok: POST {SUBSCRIBERS} email+display_name, GET its addresses -> {ADDRESS}, POST {TOKENS} "
          f"reference; the ring document connects to {ADDRESS}; every path, body and required field is "
          f"documented; the browser registers with client.online and answers; {compiled}")


if __name__ == "__main__":
    main()
