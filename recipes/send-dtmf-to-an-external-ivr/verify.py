"""Prove the claim without a network.

Claim: your call navigates someone else's phone tree by sending digits at the
moment the tree is listening.

Proof: the digits ride along with the origination, in the documented
`send_digits` parameter of the `dial` command, which the spec describes as
digits sent after the call is answered. Every character is one that parameter
allows, the string spells the route it was built from, and nothing in the
recipe uses the `send_digits` verb, which would not run until the bridge had
already ended.
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
    "SIGNALWIRE_PHONE_NUMBER": "+15550001111",
    "IVR_NUMBER": "+15550100050",
    "PUBLIC_URL": "https://recipes.example.test",
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.navigate(recipe.hold_for_a_human())

    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    assert (call["method"], call["path"]) == ("POST", PATH), call
    body = call["body"]
    assert body["command"] == "dial", body
    params = body["params"]

    # The parameter exists, and its description is the mechanism this recipe
    # depends on: digits are sent once the call is answered.
    schema = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    sd = schema["properties"]["send_digits"]
    assert "after the call is answered" in sd["description"], sd
    assert set(params) <= set(schema["properties"]), sorted(set(params) - set(schema["properties"]))

    # Every character is one the parameter allows. `W` belongs to the verb,
    # not here, so a string built for the verb would fail this.
    digits = params["send_digits"]
    assert set(digits) <= recipe.ALLOWED, sorted(set(digits) - recipe.ALLOWED)
    assert "W" not in digits, digits

    # The string spells the route, pause for pause and key for key.
    assert digits.count(",") == sum(p for p, _ in recipe.ROUTE), (digits, recipe.ROUTE)
    assert [c for c in digits if c != ","] == [k for _, k in recipe.ROUTE], digits
    # a route that presses immediately is the failure this recipe is about
    assert digits[0] == ",", digits

    # The document that runs on our side is real SWML, and contains no
    # send_digits verb: after connect it would fire once the bridge had ended.
    V.validate_swml(params["swml"])
    assert "send_digits" not in V.verb_names(params["swml"]), params["swml"]

    print(f"ok: dial carries send_digits={digits!r} (sent after answer) plus a "
          f"valid inline document; no send_digits verb anywhere")


if __name__ == "__main__":
    main()
