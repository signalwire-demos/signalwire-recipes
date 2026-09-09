"""Prove the claim without a network.

Claim: asking for `initiated`, `ringing`, `answered` and `completed` in
`StatusCallbackEvent` asks SignalWire to post those state changes of a call
to your URL. Keyed by `CallSid` and ordered by `SequenceNumber`, the callbacks
that arrive rebuild the call's life, with the duration when the completed one
carries it.

Proof: with the HTTP layer replaced by a recorder, `place` makes one POST to
the documented compat calls path with exactly the expected body. The four
events it asks for are in the list the spec's description calls valid, and the
two it leaves out are named. Then the
Flask app receives four callbacks out of order. Each carries every field the
spec's voice status callback schema requires and a `CallStatus` from its enum,
and one of them is form-encoded. Every one of the 24 arrival orders yields the
same timeline. `timeline` returns the steps in sequence order,
initiated, ringing, in-progress, completed, with the duration taken from the
completed event alone. Expected values live here, not in app.py.
"""
import itertools
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "CALL_FROM": "+15550001111",
    "CALL_URL": "https://example.com/cxml/greeting.xml",
    "STATUS_CALLBACK_URL": "https://example.com/status",
})

import verifylib as V  # noqa: E402

CALLS = "/api/laml/2010-04-01/Accounts/proj-1234/Calls"
SID = "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
TO = "+15550002222"

BASE = {"AccountSid": "proj-1234", "ApiVersion": "2010-04-01", "CallSid": SID,
        "Direction": "outbound-api", "From": "+15550001111", "To": TO,
        "CallbackSource": "call-progress-events",
        "AudioInAveragePtime": 20, "AudioInDtmfPacketCount": 0, "AudioInFlushPacketCount": 0,
        "AudioInJitterMaxVariance": 0, "AudioInJitterMinVariance": 0, "AudioInLargestJbSize": 0,
        "AudioInMos": "4.4", "AudioInMediaPacketCount": 0, "AudioInSkipPacketCount": 0,
        "AudioOutDtmfPacketCount": 0, "AudioOutMediaPacketCount": 0}


def event(seq, status, at, **extra):
    return {**BASE, "SequenceNumber": seq, "CallStatus": status, "Timestamp": at, **extra}


ARRIVAL = [  # deliberately not in sequence order
    event(3, "completed", "Wed, 02 Sep 2026 10:00:41 +0000", CallDuration=38),
    event(0, "initiated", "Wed, 02 Sep 2026 10:00:00 +0000"),
    event(2, "in-progress", "Wed, 02 Sep 2026 10:00:03 +0000"),
    event(1, "ringing", "Wed, 02 Sep 2026 10:00:01 +0000"),
]


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    import app as recipe

    # the request that asks for the four selected stages
    rec = V.Recorder(responses=[{"sid": SID, "status": "queued"}])
    recipe.client.compat.calls._http = rec
    recipe.place(TO)
    assert len(rec.calls) == 1, rec.calls
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", CALLS), call
    assert call["body"] == {"To": TO, "From": "+15550001111",
                            "Url": "https://example.com/cxml/greeting.xml",
                            "StatusCallback": "https://example.com/status",
                            "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
                            "StatusCallbackMethod": "POST"}, call["body"]
    V.assert_documented("compat", "POST", call["path"], call["body"])

    spec = V.spec("compat")
    op = spec["paths"]["/Accounts/{AccountSid}/Calls"]["post"]
    props = deref(spec, op["requestBody"]["content"]["application/json"]["schema"])["properties"]
    valid = re.search(r"Valid values: ([\w, ]+)\.", props["StatusCallbackEvent"]["description"])
    valid = {v.strip() for v in valid.group(1).split(",")}
    asked = set(call["body"]["StatusCallbackEvent"])
    assert asked <= valid, (asked, valid)
    assert valid - asked == {"ringing_forwarded", "ringing_queued"}, valid - asked
    assert "Defaults to `completed`" in props["StatusCallbackEvent"]["description"]
    assert call["body"]["StatusCallbackMethod"] in deref(spec, props["StatusCallbackMethod"])["enum"]

    # the payload, as the spec documents it
    hook = spec["webhooks"]["subpackage_calls.voice_status_callback"]["post"]
    schema = deref(spec, hook["requestBody"]["content"]["application/json"]["schema"])
    statuses = deref(spec, schema["properties"]["CallStatus"])["enum"]
    for e in ARRIVAL:
        assert set(schema["required"]) <= set(e), sorted(set(schema["required"]) - set(e))
        assert set(e) <= set(schema["properties"]), sorted(set(e) - set(schema["properties"]))
        assert e["CallStatus"] in statuses, (e["CallStatus"], statuses)
    assert "Only present on the `completed` event" in schema["properties"]["CallDuration"]["description"]
    assert "starting at 0" in schema["properties"]["SequenceNumber"]["description"]

    # four callbacks, out of order, one of them form-encoded
    client = recipe.app.test_client()
    for i, e in enumerate(ARRIVAL):
        r = client.post("/status", data=e) if i == 2 else client.post("/status", json=e)
        assert r.status_code == 204, (i, r.status_code, r.data[:100])

    life = recipe.timeline(SID)
    assert [s["status"] for s in life["steps"]] == ["initiated", "ringing", "in-progress", "completed"], life
    assert [s["seq"] for s in life["steps"]] == [0, 1, 2, 3], life
    assert life["steps"][2]["at"] == "Wed, 02 Sep 2026 10:00:03 +0000", life["steps"][2]
    assert (life["final"], life["duration"]) == ("completed", 38), life
    assert (life["direction"], life["from"], life["to"]) == ("outbound-api", "+15550001111", TO), life

    # every arrival order gives the same complete timeline
    EXPECTED_LIFE = {
        "call_sid": SID, "direction": "outbound-api", "from": "+15550001111", "to": TO,
        "steps": [{"seq": 0, "status": "initiated", "at": "Wed, 02 Sep 2026 10:00:00 +0000"},
                  {"seq": 1, "status": "ringing", "at": "Wed, 02 Sep 2026 10:00:01 +0000"},
                  {"seq": 2, "status": "in-progress", "at": "Wed, 02 Sep 2026 10:00:03 +0000"},
                  {"seq": 3, "status": "completed", "at": "Wed, 02 Sep 2026 10:00:41 +0000"}],
        "final": "completed", "duration": 38,
    }
    assert life == EXPECTED_LIFE, life
    for order in itertools.permutations(ARRIVAL):
        recipe.CALLS.clear()
        for e in order:
            client.post("/status", json=e)
        assert recipe.timeline(SID) == EXPECTED_LIFE, [e["SequenceNumber"] for e in order]
    recipe.CALLS.clear()
    for e in ARRIVAL:
        client.post("/status", json=e)
    life = recipe.timeline(SID)

    # the same timeline over HTTP, from the process that holds the store
    r = client.get(f"/calls/{SID}")
    assert r.status_code == 200 and r.get_json() == life, (r.status_code, r.get_json())

    # a call that has only started has no duration yet
    recipe.record(event(0, "initiated", "Wed, 02 Sep 2026 11:00:00 +0000", CallSid="other"))
    partial = recipe.timeline("other")
    assert partial["duration"] is None and partial["final"] == "initiated", partial

    # CallDuration is permitted on completed, not required: no duration, no crash
    recipe.record(event(1, "completed", "Wed, 02 Sep 2026 11:00:20 +0000", CallSid="other"))
    ended = recipe.timeline("other")
    assert (ended["final"], ended["duration"]) == ("completed", None), ended
    assert "CallDuration" not in schema["required"], "the spec now requires CallDuration"
    assert recipe.timeline("never") == {"call_sid": "never", "direction": None, "from": None,
                                        "to": None, "steps": [], "final": None, "duration": None}

    print(f"ok: POST {CALLS} asks for {call['body']['StatusCallbackEvent']}; four callbacks "
          f"arriving 3,0,2,1 rebuild initiated -> ringing -> in-progress -> completed with "
          f"duration 38 for {SID[:8]}...")


if __name__ == "__main__":
    main()
