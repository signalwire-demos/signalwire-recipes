"""Prove the claim without a network.

Claim: three REST calls take a number you own elsewhere through verification
as an outbound caller ID: create it, submit the code, redial if needed.

Proof: with the HTTP layer replaced by a recorder, each helper makes exactly
one request to the documented verified-caller-ID path with the documented
method and body. `create` POSTs `number` and `name`, `submit_verification`
PUTs `verification_code` to the id's verification path, and
`redial_verification` POSTs to the same path with no body. Every body field
is documented and the required ones are present. Expected values live here,
not in app.py.
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

BASE = "/api/relay/rest/verified_caller_ids"
CID = "0f8fad5b-d9cb-469f-a165-70867728950e"
NUMBER, NAME, CODE = "+15557654321", "Shop mobile", "482913"


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.verified_callers._http = rec

    recipe.start(NUMBER, NAME)
    recipe.confirm(CID, CODE)
    recipe.resend(CID)
    assert len(rec.calls) == 3, rec.calls

    create, confirm, resend = rec.calls
    assert (create["method"], create["path"]) == ("POST", BASE), create
    assert create["body"] == {"number": NUMBER, "name": NAME}, create
    V.assert_documented("rest", "POST", BASE, create["body"])

    vpath = f"{BASE}/{CID}/verification"
    assert (confirm["method"], confirm["path"]) == ("PUT", vpath), confirm
    assert confirm["body"] == {"verification_code": CODE}, confirm
    V.assert_documented("rest", "PUT", vpath, confirm["body"])

    assert (resend["method"], resend["path"]) == ("POST", vpath), resend
    assert resend["body"] is None, resend
    V.assert_documented("rest", "POST", vpath, None)

    # the spec's own required lists, so the README's "number is required" holds
    s = V.spec("rest")["paths"][BASE]["post"]["requestBody"]["content"]
    schema = s["application/json"]["schema"]
    if "$ref" in schema:
        schema = V.spec("rest")["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert schema.get("required") == ["number"], schema.get("required")

    print(f"ok: POST {BASE} {{number, name}}; PUT .../{CID[:8]}.../verification "
          f"{{verification_code}}; POST the same path to redial; all documented")


if __name__ == "__main__":
    main()
