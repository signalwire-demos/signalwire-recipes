"""Prove the claim without a network.

Claim: a SWML webhook resource whose `primary_request_url` is your agent's URL
is a thing a browser can dial: you list its Fabric addresses over REST and mint
a guest token whose `allowed_addresses` names one, with no Dashboard step.

Proof: the HTTP layer is a recorder. `register` makes one POST to the
documented SWML webhooks path with exactly `name`, `used_for`,
`primary_request_url` and `primary_request_method`. It then asks for the
resource's addresses; the first answer is empty, it waits once, and the second
carries the address. A resource that never lists one fails after five tries
with a message, and no token is minted. `guest_token` makes one POST to the
documented guest tokens path with exactly the one address id and an
`expire_at` fifteen minutes after the injected clock, a clock of zero
included. The spec requires `primary_request_url` on the resource and
`allowed_addresses` on the token, caps the list at ten, and documents `token`
and `refresh_token` in the response. Expected values live here, not in app.py.
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
    "AGENT_URL": "https://signalwire:secret@agent.example.com/front-desk/",
    "TOKEN_TTL_SECONDS": "900",
})

import verifylib as V  # noqa: E402

WEBHOOKS = "/api/fabric/resources/swml_webhooks"
GUESTS = "/api/fabric/guests/tokens"
RID = "3c9a1f2e-4b5d-4c6e-9f70-8192a3b4c5d6"
ADDR = "7d1e2f3a-4b5c-4d6e-8f90-a1b2c3d4e5f6"
NOW = 1_788_350_400


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

    ADDRESS = {"id": ADDR, "name": "front-desk", "display_name": "front-desk",
               "type": "app", "channels": {"audio": "/public/front-desk?channel=audio"}}
    rec = V.Recorder(responses=[
        {"id": RID, "display_name": "front-desk", "type": "swml_webhook"},
        {"data": []},                       # the list lags the create
        {"data": [ADDRESS]},
        {"token": "eyJ-verifier-only", "refresh_token": "rt-verifier-only"},
    ])
    recipe.client.fabric.swml_webhooks._http = rec
    recipe.client.fabric.tokens._http = rec
    waits = []

    resource_id, address = recipe.register(wait=waits.append)
    assert (resource_id, address) == (RID, ADDRESS), (resource_id, address)
    assert waits == [1], waits
    minted = recipe.guest_token(address["id"], now=NOW)
    assert minted == {"token": "eyJ-verifier-only", "refresh_token": "rt-verifier-only"}, minted

    expected = [("POST", WEBHOOKS), ("GET", f"{WEBHOOKS}/{RID}/addresses"),
                ("GET", f"{WEBHOOKS}/{RID}/addresses"), ("POST", GUESTS)]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    create, listing, _, token = rec.calls

    # a resource that never lists an address fails clearly, and mints nothing.
    # Five tries and four waits are the verifier's numbers, not the app's; a
    # separate recorder on the token client proves no token was asked for.
    assert recipe.ADDRESS_TRIES == 5, recipe.ADDRESS_TRIES
    rec2 = V.Recorder(responses=[{"id": "r-2"}] + [{"data": []}] * 5)
    tokens2 = V.Recorder(responses=[])
    recipe.client.fabric.swml_webhooks._http = rec2
    recipe.client.fabric.tokens._http = tokens2
    waits2 = []
    try:
        recipe.register(wait=waits2.append)
    except RuntimeError as e:
        assert "r-2" in str(e) and "5 tries" in str(e), str(e)
    else:
        raise AssertionError("an address-less resource did not fail")
    assert [c["method"] for c in rec2.calls] == ["POST"] + ["GET"] * 5, rec2.calls
    assert waits2 == [1, 1, 1, 1], waits2
    assert tokens2.calls == [], "no token may be minted for a resource with no address"
    recipe.client.fabric.swml_webhooks._http = rec

    # a clock of zero is a clock, not a missing argument
    rec3 = V.Recorder(responses=[{"token": "t", "refresh_token": "r"}])
    recipe.client.fabric.tokens._http = rec3
    recipe.guest_token(ADDR, now=0)
    assert rec3.calls[0]["body"] == {"allowed_addresses": [ADDR], "expire_at": 900}, rec3.calls
    assert create["body"] == {"name": "front-desk", "used_for": "calling",
                              "primary_request_url": "https://signalwire:secret@agent.example.com/front-desk/",
                              "primary_request_method": "POST"}, create["body"]
    assert listing["body"] is None and listing["params"] is None, listing
    assert token["body"] == {"allowed_addresses": [ADDR], "expire_at": NOW + 900}, token["body"]

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", WEBHOOKS, create["body"])
    V.assert_documented("rest", "GET", "/api/fabric/resources/{id}/addresses", None)
    V.assert_documented("rest", "POST", GUESTS, token["body"])
    hook = body_schema(spec, WEBHOOKS)
    assert hook["required"] == ["primary_request_url"], hook["required"]
    assert "calling" in deref(spec, hook["properties"]["used_for"])["enum"]
    assert "POST" in deref(spec, hook["properties"]["primary_request_method"])["enum"]
    guest = body_schema(spec, GUESTS)
    assert guest["required"] == ["allowed_addresses"], guest["required"]
    allowed = deref(spec, guest["properties"]["allowed_addresses"])
    assert "up to 10" in allowed["description"], allowed["description"]
    code, props = response_props(spec, GUESTS, "post")
    assert code == "201" and {"token", "refresh_token"} <= set(props), (code, sorted(props))
    code, props = response_props(spec, "/api/fabric/resources/{id}/addresses", "get")
    assert code == "200" and {"id", "name", "channels"} <= set(props), (code, sorted(props))
    assert set(address) <= set(props), sorted(set(address) - set(props))

    print(f"ok: POST {WEBHOOKS} pointing at the agent URL, GET its addresses, POST {GUESTS} "
          f"allowing {ADDR[:8]}... until now+900s; every path, body and required field is documented")


if __name__ == "__main__":
    main()
