"""Prove the claim without a network.

Claim: one GET to the lookup path returns a number's details, and
`include=carrier,cnam` is what asks for carrier and caller-ID name.

Proof: with the HTTP layer replaced by a recorder, `enrich` makes exactly one
GET to the documented lookup path with `include` set to `carrier,cnam`.
`check` makes one GET with no query at all. The vendored spec documents the
path and the `include` parameter, and its description of `include` names
both values. The spec's response schema carries `valid_number`,
`e164`, the formatted forms, `country_code`, `number_type`, a `carrier` object
with `linetype` and a `cnam` object with `caller_id`. Expected values live
here, not in app.py.
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

NUMBER = "+15557654321"
TEMPLATE = "/api/relay/rest/lookup/phone_number/{e164_number}"
PATH = TEMPLATE.replace("{e164_number}", NUMBER)


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.lookup._http = rec

    recipe.enrich(NUMBER)
    assert len(rec.calls) == 1, rec.calls  # one helper, one request
    recipe.check(NUMBER)
    assert len(rec.calls) == 2, rec.calls
    rich, plain = rec.calls

    assert (rich["method"], rich["path"]) == ("GET", PATH), rich
    assert rich["params"] == {"include": "carrier,cnam"}, rich
    V.assert_documented("rest", "GET", PATH, None, rich["params"])

    assert (plain["method"], plain["path"]) == ("GET", PATH), plain
    assert plain["params"] is None, plain

    # the spec's own words for include, and the response fields it promises
    op = V.spec("rest")["paths"][TEMPLATE]["get"]
    include = next(p for p in op["parameters"] if p["name"] == "include")
    assert "carrier" in include["description"] and "cnam" in include["description"]
    schemas = V.spec("rest")["components"]["schemas"]
    resp = op["responses"]["200"]["content"]["application/json"]["schema"]
    resp = schemas[resp["$ref"].split("/")[-1]] if "$ref" in resp else resp
    props = resp["properties"]
    advertised = {"carrier", "cnam", "valid_number", "e164", "number_type", "country_code",
                  "national_number_formatted", "international_number_formatted", "timezones"}
    assert advertised <= set(props), sorted(advertised - set(props))

    def obj(name):
        node = props[name]
        return schemas[node["$ref"].split("/")[-1]] if "$ref" in node else node
    carrier = {"lrn", "spid", "ocn", "lata", "city", "state", "jurisdiction", "lec", "linetype"}
    assert carrier <= set(obj("carrier")["properties"]), sorted(obj("carrier")["properties"])
    assert "caller_id" in obj("cnam")["properties"], sorted(obj("cnam")["properties"])

    print(f"ok: GET {PATH}?include=carrier,cnam and once without a query; include is "
          f"documented with those two values; the response schema carries the nine "
          f"carrier fields, cnam.caller_id and the formatted fields")


if __name__ == "__main__":
    main()
