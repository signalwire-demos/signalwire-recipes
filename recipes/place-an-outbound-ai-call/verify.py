"""Prove the claim without a network.

Claim: one REST `dial` command carries an AI agent's SWML inside the request,
and that document's `ai.params` carry `direction: outbound` and
`wait_for_user: true`.

Proof: with the HTTP layer replaced by a recorder, `place()` makes exactly one
POST to the documented calling path with `command: dial`. Every parameter is a
documented property of the SWML dial variant and the required ones are present.
The inline document validates against the bundled schema. Its `ai.params` carry
the two values and an `outbound_attention_timeout` inside the schema's range.
Expected values live here, not in app.py.
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
    "PUBLIC_URL": "https://recipes.example.test",
})
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
TO = "+15552223333"


def documented_dial_params():
    s = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    return set(s.get("properties", {})), set(s.get("required", []))


def main():
    V.sdk_banner()
    import app as recipe

    V.assert_basic_auth_from_env(recipe.agent)
    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.place(TO)

    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    assert (call["method"], call["path"]) == ("POST", PATH), call
    V.assert_documented("rest", "POST", PATH, None)
    body = call["body"]
    assert body["command"] == "dial", body
    params = body["params"]

    props, required = documented_dial_params()
    assert {"from", "swml"} <= required, required  # the README says so; the spec must
    unknown = set(params) - props
    assert not unknown, f"undocumented dial params: {sorted(unknown)}"
    for key in required:
        assert key in params, f"the SWML dial variant requires {key}"
    assert params["to"] == TO and params["from"] == "+15550001111", params
    assert "url" not in params, params  # the document travels inline, not by URL

    # the document that rides inside the request is the agent's, and valid
    doc = params["swml"]
    V.validate_swml(doc)
    assert doc["sections"]["main"][0] == {"answer": {}}, doc["sections"]["main"][0]
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    assert ai["prompt"]["pom"][0]["title"] == "Role", ai["prompt"]
    p = ai["params"]
    assert p["direction"] == "outbound", p
    assert p["wait_for_user"] is True, p
    # inside the range the bundled SWML schema gives for the attention window
    rng = V.swml_schema()["$defs"]["AIParams"]["properties"]["outbound_attention_timeout"]
    lo, hi = rng["minimum"], rng["maximum"]
    assert lo <= p["outbound_attention_timeout"] <= hi, (lo, p, hi)

    events = V.spec("rest")["components"]["schemas"][
        "CallingCallCreateParamsSwmlStatusEventsItems"]["enum"]
    assert set(params["status_events"]) <= set(events), params["status_events"]

    # the plain-SWML surface carries the same two params
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    yp = V.first(y, "ai")["params"]
    assert (yp["direction"], yp["wait_for_user"]) == ("outbound", True), yp

    print(f"ok: POST {PATH} command=dial to {TO} with the agent's SWML inline; "
          f"ai.params direction=outbound, wait_for_user=true, "
          f"outbound_attention_timeout={p['outbound_attention_timeout']}")


if __name__ == "__main__":
    main()
