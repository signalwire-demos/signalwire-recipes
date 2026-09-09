"""Prove the claim without a network.

Claim: one SWML webhook serves several numbers. Your handler reads the dialed
number from the documented inbound call webhook and the clock in that line's
zone. It returns the document for that number at that hour.

Proof: drive the Flask app with its test client and a frozen clock. Two
payloads shaped like the spec's inbound call webhook, every required field
present and nothing undocumented, differ only in the dialed number. At one
instant, 16:30 UTC, the sales line in Denver is open at 10:30 and the workshop
line in Los Angeles is open at 09:30. Each document connects to its own
destination. At another instant, 01:00 UTC, both are closed and each document
plays its own hours and hangs up. A number in neither line plays a
not-in-service message. Every document validates. Expected values live here,
not in app.py.
"""
import os
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ["CONNECT_TIMEOUT"] = "25"
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")

import verifylib as V  # noqa: E402

SALES, WORKSHOP, NOBODY = "+15550001111", "+15550002222", "+15550009999"
OPEN_AT = datetime(2026, 9, 2, 16, 30, tzinfo=timezone.utc)    # 10:30 Denver, 09:30 LA
CLOSED_AT = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)    # 19:00 Denver, 18:00 LA
EDGE = datetime(2026, 9, 2, 22, 59, tzinfo=timezone.utc)       # 16:59 Denver open, 15:59 LA open
PAST_EDGE = datetime(2026, 9, 2, 23, 0, tzinfo=timezone.utc)   # 16:00 LA, the workshop is closed


def payload(to):
    return {"call": {"call_id": "c1", "node_id": "n1", "segment_id": "s1", "call_state": "created",
                     "direction": "inbound", "type": "phone", "from": "+15550003333", "to": to,
                     "from_number": "+15550003333", "to_number": to, "headers": [],
                     "project_id": "proj-1234", "space_id": "space-1"},
            "vars": {}, "envs": {}, "params": {}}


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    import app as recipe

    # the fixture is the documented webhook
    spec = V.spec("rest")
    hook = spec["webhooks"]["subpackage_callingWebhooks.inbound_call_webhook"]["post"]
    schema = deref(spec, hook["requestBody"]["content"]["application/json"]["schema"])
    call_schema = deref(spec, schema["properties"]["call"])
    sample = payload(SALES)
    assert set(schema["required"]) <= set(sample), schema["required"]
    assert set(sample) <= set(schema["properties"]), sorted(set(sample) - set(schema["properties"]))
    assert set(call_schema["required"]) <= set(sample["call"]), call_schema["required"]
    assert set(sample["call"]) <= set(call_schema["properties"]), \
        sorted(set(sample["call"]) - set(call_schema["properties"]))
    assert "destination" in deref(spec, call_schema["properties"]["to"])["description"]
    assert "phone" in deref(spec, call_schema["properties"]["type"])["enum"]

    class FrozenDatetime(datetime):
        frozen = OPEN_AT

        @classmethod
        def now(cls, tz=None):
            return cls.frozen.astimezone(tz) if tz else cls.frozen

    real = recipe.datetime
    recipe.datetime = FrozenDatetime
    client = recipe.app.test_client()
    import base64
    creds = base64.b64encode(b"signalwire:verify-only-password").decode()
    AUTH = {"Authorization": "Basic " + creds}

    def fetch(to, at):
        FrozenDatetime.frozen = at
        r = client.post("/swml", json=payload(to), headers=AUTH)
        assert r.status_code == 200, (to, at, r.status_code, r.data[:80])
        doc = r.get_json()
        V.validate_swml(doc)
        return doc

    try:
        # the webhook is behind the basic auth SignalWire carries in the URL
        # (sol r2): no credentials, or the wrong ones, get 401 and no document
        FrozenDatetime.frozen = OPEN_AT
        assert client.post("/swml", json=payload(SALES)).status_code == 401
        wrong = base64.b64encode(b"signalwire:wrong").decode()
        assert client.post("/swml", json=payload(SALES),
                           headers={"Authorization": "Basic " + wrong}).status_code == 401

        # open: greeting, then connect to that line's own destination
        for to, dest, greeting in ((SALES, "+15550100001", "say:Ridgeline Cycles sales, one moment."),
                                   (WORKSHOP, "+15550100002", "say:Ridgeline Cycles workshop, one moment.")):
            doc = fetch(to, OPEN_AT)
            assert V.verb_names(doc) == ["answer", "play", "connect", "hangup"], (to, V.verb_names(doc))
            assert V.first(doc, "connect") == {"to": dest, "timeout": 25}, (to, V.first(doc, "connect"))
            assert V.first(doc, "play") == {"url": greeting}, (to, V.first(doc, "play"))

        # closed: the hours, no connect
        for to, hours in ((SALES, "9 AM to 6 PM"), (WORKSHOP, "8 AM to 4 PM")):
            doc = fetch(to, CLOSED_AT)
            assert V.verb_names(doc) == ["answer", "play", "hangup"], (to, V.verb_names(doc))
            assert hours in V.first(doc, "play")["url"], (to, V.first(doc, "play"))

        # the clock is judged in each line's own zone: two instants a minute apart
        assert "connect" in V.verb_names(fetch(WORKSHOP, EDGE)), "15:59 in Los Angeles is open"
        assert "connect" not in V.verb_names(fetch(WORKSHOP, PAST_EDGE)), "16:00 in Los Angeles is closed"
        assert "connect" in V.verb_names(fetch(SALES, PAST_EDGE)), "17:00 in Denver is open"

        # a number in neither line
        doc = fetch(NOBODY, OPEN_AT)
        assert V.verb_names(doc) == ["answer", "play", "hangup"], V.verb_names(doc)
        assert V.first(doc, "play")["url"] == "say:This number is not in service.", V.first(doc, "play")
    finally:
        recipe.datetime = real

    # to_number wins when present; to is the fallback the spec documents for other call types
    assert recipe.dialed({"to": "sip:x@y", "to_number": SALES}) == SALES
    assert recipe.dialed({"to": SALES}) == SALES

    print(f"ok: at 16:30 UTC {SALES} connects to sales and {WORKSHOP} to the workshop; at 01:00 UTC "
          f"both play their hours; 15:59 and 16:00 in Los Angeles fall on opposite sides of the "
          f"workshop's close; an unknown number is not in service")


if __name__ == "__main__":
    main()
