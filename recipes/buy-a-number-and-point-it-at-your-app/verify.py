"""Prove the claim without a network.

Claim: search by area code or pattern, purchase, and assign the number's call
handler, all over REST.

Proof: with the HTTP layer replaced by a recorder, provision() makes exactly
three documented requests in order - GET search with documented query params,
POST purchase with the required `number`, PUT update with documented handler
fields - and the URL the number is pointed at is the one we passed.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"data": [{"e164": "+14155550123"}, {"e164": "+14155550124"}]},
        {"id": "pn-1", "number": "+14155550123"},
        {"id": "pn-1", "number": "+14155550123", "call_handler": "relay_script"},
    ]))
    bought = recipe.provision("415", "https://recipes.example.test/ivr")
    assert bought["number"] == "+14155550123"

    search, purchase, update = rec.calls
    assert (search["method"], search["path"]) == ("GET", "/api/relay/rest/phone_numbers/search"), search
    V.assert_documented("rest", "GET", search["path"], params=search["params"])
    assert search["params"]["areacode"] == "415" and search["params"]["number_type"] == "local", search

    assert (purchase["method"], purchase["path"]) == ("POST", "/api/relay/rest/phone_numbers"), purchase
    V.assert_documented("rest", "POST", purchase["path"], body=purchase["body"])
    assert purchase["body"] == {"number": "+14155550123"}, purchase

    assert (update["method"], update["path"]) == ("PUT", "/api/relay/rest/phone_numbers/pn-1"), update
    V.assert_documented("rest", "PUT", update["path"], body=update["body"])
    assert update["body"]["call_handler"] == "relay_script"
    assert update["body"]["call_relay_script_url"] == "https://recipes.example.test/ivr"
    print("ok: GET search(areacode) -> POST purchase(number) -> PUT call_handler=relay_script, call_relay_script_url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
