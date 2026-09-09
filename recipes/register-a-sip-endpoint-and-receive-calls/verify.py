"""Prove the claim without a network.

Claim: a subscriber's SIP credential is a username and password a softphone
registers with, created with one POST. A SWML `connect` to the subscriber's
Fabric address is the document that sends a call to it.

Proof: with the HTTP layer replaced by a recorder, `create_subscriber` makes
one POST to the documented subscribers path and one GET of its addresses.
`add_sip_credential` makes one POST to the documented subscriber SIP endpoints
path with exactly `username`, `password` and `caller_id`. The spec requires
exactly `username` and `password` there. It documents the other fields the
recipe leaves out, and the response. The password is read from the environment
inside the function, and a missing one stops the call before any request. The
document validates, contains answer, connect, hangup, and its `connect.to` is
the address; the bundled schema lists a Call Fabric Resource address among the
forms `connect.to` takes. Expected values live here, not in app.py.
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
    "SUBSCRIBER_EMAIL": "workshop@ridgeline.example",
    "SIP_USERNAME": "workshop-desk",
    "SIP_PASSWORD": "verifier-only-sip-password",
    "SIP_CALLER_ID": "+15550001111",
})

import verifylib as V  # noqa: E402

SUBSCRIBERS = "/api/fabric/resources/subscribers"
RID = "2b3c4d5e-6f70-4a81-9b2c-3d4e5f6a7b8c"
ADDRESS = "/private/workshop"


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

    endpoint_path = f"{SUBSCRIBERS}/{RID}/sip_endpoints"
    rec = V.Recorder(responses=[
        {"id": RID, "display_name": "Workshop desk", "type": "subscriber"},
        {"data": [{"id": "addr-1", "name": ADDRESS, "display_name": "Workshop desk",
                   "type": "subscriber", "channels": {"audio": f"{ADDRESS}?channel=audio"}}]},
        {"id": "sip-1", "username": "workshop-desk", "caller_id": "+15550001111",
         "send_as": None, "ciphers": [], "codecs": [], "encryption": "default"},
    ])
    recipe.client.fabric.subscribers._http = rec

    resource_id, address = recipe.create_subscriber()
    assert (resource_id, address) == (RID, ADDRESS), (resource_id, address)
    credential = recipe.add_sip_credential(resource_id)
    assert credential["username"] == "workshop-desk", credential

    expected = [("POST", SUBSCRIBERS), ("GET", f"{SUBSCRIBERS}/{RID}/addresses"), ("POST", endpoint_path)]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    create, listing, endpoint = rec.calls
    assert create["body"] == {"email": "workshop@ridgeline.example", "display_name": "Workshop desk"}
    assert listing["body"] is None and listing["params"] is None, listing
    assert endpoint["body"] == {"username": "workshop-desk", "password": "verifier-only-sip-password",
                                "caller_id": "+15550001111"}, endpoint["body"]

    # no password, no request
    try:
        saved = os.environ.pop("SIP_PASSWORD")
        try:
            recipe.add_sip_credential(resource_id)
        finally:
            os.environ["SIP_PASSWORD"] = saved
    except SystemExit as e:
        assert "SIP_PASSWORD" in str(e), str(e)
    else:
        raise AssertionError("a credential without a password was requested")
    assert len(rec.calls) == 3, rec.calls

    spec = V.spec("rest")
    doc_path = f"{SUBSCRIBERS}/{{fabric_subscriber_id}}/sip_endpoints"
    V.assert_documented("rest", "POST", SUBSCRIBERS, create["body"])
    V.assert_documented("rest", "GET", "/api/fabric/resources/{id}/addresses", None)
    V.assert_documented("rest", "POST", doc_path, endpoint["body"])
    cred = body_schema(spec, doc_path)
    assert set(cred["required"]) == {"username", "password"}, cred["required"]
    assert {"caller_id", "send_as", "ciphers", "codecs", "encryption"} <= set(cred["properties"]), sorted(cred["properties"])
    assert set(deref(spec, cred["properties"]["encryption"])["enum"]) == {"required", "optional", "default"}
    op = spec["paths"][doc_path]["post"]
    resp = deref(spec, op["responses"]["201"]["content"]["application/json"]["schema"])
    assert {"id", "username", "caller_id", "encryption"} <= set(resp["properties"]), sorted(resp["properties"])
    assert body_schema(spec, SUBSCRIBERS)["required"] == ["email"]

    # the document that rings the softphone
    doc = recipe.ring(address).get_document()
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "connect", "hangup"], V.verb_names(doc)
    assert V.first(doc, "connect") == {"to": ADDRESS, "timeout": 30}, V.first(doc, "connect")
    to_desc = V.swml_schema()["$defs"]["ConnectDeviceSingle"]["properties"]["to"]["description"]
    assert "Call Fabric Resource address" in to_desc, to_desc

    print(f"ok: POST {SUBSCRIBERS}, GET its addresses -> {ADDRESS}, POST .../sip_endpoints with "
          f"username, password and caller_id; the spec requires exactly the two; the ring document "
          f"connects to {ADDRESS}")


if __name__ == "__main__":
    main()
