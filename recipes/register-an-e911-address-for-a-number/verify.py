"""Prove the claim without a network.

Claim: two POSTs and one GET create an emergency address with the fields the
spec requires, find the number's id, and attach the newly created address to
the number.

Proof: the HTTP layer is a recorder that answers the create with an id, the
numbers list with two numbers, and the attach with nothing. `register` makes
the three requests in that order, and the numbers list is filtered with the
spec's `filter_number` query. The create body carries exactly the nine
fields the spec requires plus `emergency_enabled: true` and the three optional
fields passed, all documented. The spec's required set for the create equals
the nine names this file expects. The attach body carries the id the create
returned, which is the spec's whole required list for that call. Expected
values live here, not in app.py.
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
})

import verifylib as V  # noqa: E402

ADDRESSES = "/api/relay/rest/addresses"
NUMBERS = "/api/relay/rest/phone_numbers"
NUMBER, NUMBER_ID = "+15557654321", "3fa85f64-5717-4562-b3fc-2c963f66afa6"
ADDRESS_ID = "9b2e4c1a-7d3f-4e8b-a1c2-5d6e7f8a9b0c"
E911 = f"{NUMBERS}/{NUMBER_ID}/e911_address"
REQUIRED = {"label", "country", "first_name", "last_name", "street_number",
            "street_name", "city", "state", "postal_code"}
FIELDS = dict(label="Ridgeline Cycles workshop", first_name="Dana",
              last_name="Whitfield", street_number="1200", street_name="Harbor Way",
              city="Portland", state="OR", postal_code="97209")
OPTIONAL = dict(address_type="Suite", address_number="4", auto_correct_address=True)


def schema_for(path, method):
    spec = V.spec("rest")
    schema = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return set(schema.get("required", [])), set(schema.get("properties", {}))


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[
        {"id": ADDRESS_ID, "label": FIELDS["label"]},
        {"data": [{"id": "other", "number": "+15550000000"},
                  {"id": NUMBER_ID, "number": NUMBER}]},
        {},
    ])
    recipe.client.addresses._http = rec
    recipe.client.phone_numbers._http = rec

    recipe.register(NUMBER, **FIELDS, **OPTIONAL)
    assert [(c["method"], c["path"]) for c in rec.calls] == [
        ("POST", ADDRESSES), ("GET", NUMBERS), ("POST", E911)], \
        [(c["method"], c["path"]) for c in rec.calls]
    create, listing, attach = rec.calls

    # the create: the spec's nine required fields are the nine this file names
    required, props = schema_for(ADDRESSES, "post")
    assert required == REQUIRED, sorted(required ^ REQUIRED)
    body = create["body"]
    assert REQUIRED <= set(body), sorted(REQUIRED - set(body))
    assert set(body) <= props, sorted(set(body) - props)
    assert {k: body[k] for k in FIELDS} == FIELDS, body
    assert body["country"] == "US" and body["emergency_enabled"] is True, body
    assert {k: body[k] for k in OPTIONAL} == OPTIONAL, body
    V.assert_documented("rest", "POST", ADDRESSES, body)

    # the lookup: one GET of the documented numbers list, filtered to the number
    assert listing["params"] == {"filter_number": NUMBER}, listing
    V.assert_documented("rest", "GET", NUMBERS, None, listing["params"])

    # the attach: the id the create returned, and nothing else
    assert attach["body"] == {"e911_address_id": ADDRESS_ID}, attach
    required, props = schema_for(NUMBERS + "/{id}/e911_address", "post")
    assert required == {"e911_address_id"}, required
    assert set(attach["body"]) <= props, sorted(set(attach["body"]) - props)
    V.assert_documented("rest", "POST", E911, attach["body"])

    print(f"ok: POST {ADDRESSES} with the spec's nine required fields plus "
          f"emergency_enabled and three options; GET {NUMBERS}; POST the number's "
          f"e911_address with the id the create returned")


if __name__ == "__main__":
    main()
