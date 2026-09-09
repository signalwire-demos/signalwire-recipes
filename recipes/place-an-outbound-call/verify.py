"""Prove the claim without a network.

Claim: your backend originates a call over REST and hands it a document to run
when answered.

Proof: with the HTTP layer replaced by a recorder, `place()` makes exactly one
POST to the documented calling path with the `dial` command; every parameter is
a documented property of the SWML dial variant and the required ones are
present; and the document handed over is itself valid SWML, so the call has
something real to run.
"""
import json
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
    "PUBLIC_URL": "https://recipes.example.test",
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"


def documented_dial_params():
    """The SWML dial variant, read from the spec rather than assumed."""
    s = V.spec("rest")
    schema = s["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    return set(schema.get("properties", {})), set(schema.get("required", []))


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.place("+15552223333", "Your bike is ready.")

    # Exactly one request, to the documented path.
    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    body = call["body"]
    assert (call["method"], call["path"]) == ("POST", PATH), call
    V.assert_documented("rest", "POST", PATH, None)

    # The command discriminator the platform switches on.
    assert body["command"] == "dial", body
    params = body["params"]

    # Every parameter is documented, and the required ones are there. The
    # body schema for this path is a oneOf, so assert_documented cannot check
    # the params for us: read the variant out of the spec and check it here.
    props, required = documented_dial_params()
    unknown = set(params) - props
    assert not unknown, f"undocumented dial params: {sorted(unknown)}"
    for key in required:
        assert key in params, f"the SWML dial variant requires {key}"

    # The spec's mechanical `required` list omits `to`, so deleting the
    # destination would still pass a documented-fields check. Assert the
    # values, not just that the keys are allowed.
    assert params["to"] == "+15552223333", params
    assert params["from"] == recipe.FROM, params

    # "hands it a document": the SWML travels in the request, not behind a URL.
    assert "swml" in params and "url" not in params, params
    V.validate_swml(params["swml"])
    assert V.verb_names(params["swml"]) == ["answer", "play", "hangup"], params["swml"]

    # Lifecycle reporting, with only documented event names.
    events = V.spec("rest")["components"]["schemas"][
        "CallingCallCreateParamsSwmlStatusEventsItems"]["enum"]
    assert set(params["status_events"]) <= set(events), params["status_events"]
    assert params["status_url"].endswith("/call-status"), params

    # Ring timeout inside the documented bounds.
    t = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"][
        "properties"]["timeout"]
    assert t["minimum"] <= params["timeout"] <= t["maximum"], params["timeout"]

    print(f"ok: POST {PATH} command=dial with {sorted(params)}; "
          f"the inline document is valid SWML "
          f"({' -> '.join(V.verb_names(params['swml']))})")


if __name__ == "__main__":
    main()
