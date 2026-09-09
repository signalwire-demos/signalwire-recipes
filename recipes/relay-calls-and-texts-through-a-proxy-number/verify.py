"""Prove the claim without a network.

Claim: with A and B paired on proxy P, a call from either to P is a `connect`
to the other with `from` set to P, and a text from either to P is a `reply`
to the other from P, so neither party sees the other's number. A stranger
calling P is told the number is not active and hung up on; a stranger texting
P gets an empty document. Pairing is behind a server-held key.

Proof: the Flask routes are driven with payloads shaped like the spec's inbound
call and inbound message webhooks, after a module reload so the sessions come
from the file. Every document validates against the bundled schema, whose
`connect.from` description is quoted, and the messaging documents are checked
against the documented Messaging method set instead. Both webhook
routes refuse an unauthenticated request and `/pair` refuses a missing or wrong
key. The TypeScript surface renders the same documents behind the same gates.
Expected values live here, not in app.py.
"""
import base64
import importlib
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
SESSIONS = pathlib.Path(tempfile.mkdtemp()) / "proxy-sessions.json"
USER, PASSWORD, KEY = "recipes", "pw", "pair-key"
PROXY = "+15550001111"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SWML_BASIC_AUTH_USER": USER,
    "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
    "PROXY_NUMBER": PROXY,
    "PROXY_ADMIN_KEY": KEY,
    "SESSIONS_PATH": str(SESSIONS),
})

import verifylib as V  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}
ALICE, BOB, STRANGER = "+14155550123", "+13105550199", "+12125550100"
CAROL, DAVE = "+16465550177", "+17185550142"
ALICE_SPELLED = "+1 (415) 555-0123"   # the same participant, as a form might send it
TEXT = "Running ten minutes late."
NOT_ACTIVE = "This number is not active for your call."


def inbound_call(caller):
    return {"call": {"call_id": "c-1", "node_id": "n", "segment_id": "s",
                     "call_state": "created", "direction": "inbound", "type": "phone",
                     "from": caller, "to": PROXY, "headers": [],
                     "project_id": "proj-1234", "space_id": "sp-1"},
            "vars": {}, "envs": {}, "params": {}}


def inbound_text(sender, body):
    return {"message": {"message_id": "m-1", "project_id": "proj-1234", "space_id": "sp-1",
                        "direction": "inbound", "type": "sms", "from": sender, "to": PROXY,
                        "body": body, "media": [], "segments": 1,
                        "timestamp": "2026-09-05T09:00:00Z"},
            "vars": {}, "params": {}}


def main():
    V.sdk_banner()
    import app as recipe

    web = recipe.app.test_client()

    # pairing is behind the key: no key and a wrong key change nothing
    body = {"a": ALICE, "b": BOB}
    assert web.post("/pair", json=body).status_code == 403
    assert web.post("/pair", json=body, headers={"X-Proxy-Key": "nope"}).status_code == 403
    assert not SESSIONS.exists()
    paired = web.post("/pair", json=body, headers={"X-Proxy-Key": KEY})
    assert paired.status_code == 200, paired.status_code
    assert len(paired.get_json()["keys"]) == 2
    assert len(json.loads(SESSIONS.read_text(encoding="utf-8"))) == 2

    # the webhooks are other requests to another process: reload
    recipe = importlib.reload(recipe)
    web = recipe.app.test_client()

    def call(caller):
        r = web.post("/call", json=inbound_call(caller), headers=AUTH)
        assert r.status_code == 200, r.status_code
        doc = r.get_json()
        V.validate_swml(doc)
        return doc

    def text(sender, body=TEXT):
        r = web.post("/message", json=inbound_text(sender, body), headers=AUTH)
        assert r.status_code == 200, r.status_code
        doc = r.get_json()
        # the bundled schema is the Calling one: it refuses `reply` and accepts
        # `send_sms`, so a messaging document is checked against the method set
        V.assert_messaging_document(doc)
        return doc

    # a call from either party reaches the other, showing the proxy
    for me, them in ((ALICE, BOB), (BOB, ALICE)):
        doc = call(me)
        assert V.verb_names(doc) == ["connect"], doc
        assert V.first(doc, "connect") == {"to": them, "from": PROXY}, doc
    # a stranger hears the number is not active, then the call ends
    doc = call(STRANGER)
    assert V.verb_names(doc) == ["answer", "play", "hangup"], doc
    assert V.first(doc, "play") == {"url": f"say:{NOT_ACTIVE}"}, doc

    # a text from either party reaches the other, from the proxy
    for me, them in ((ALICE, BOB), (BOB, ALICE)):
        doc = text(me)
        assert V.verb_names(doc) == ["reply"], doc
        assert V.first(doc, "reply") == {"to": them, "from": PROXY,
                                         "body": TEXT}, doc
    # a stranger's text is an empty document
    assert text(STRANGER)["sections"]["main"] == []

    # a participant is in one pairing at a time: re-pairing Alice with Carol
    # removes Bob's route back to her, so Bob is a stranger now
    assert web.post("/pair", json={"a": ALICE, "b": CAROL},
                    headers={"X-Proxy-Key": KEY}).status_code == 200
    recipe = importlib.reload(recipe)
    web = recipe.app.test_client()
    assert V.first(call(ALICE), "connect") == {"to": CAROL, "from": PROXY}
    assert V.first(call(CAROL), "connect") == {"to": ALICE, "from": PROXY}
    assert V.verb_names(call(BOB)) == ["answer", "play", "hangup"]
    assert text(BOB)["sections"]["main"] == []
    assert len(json.loads(SESSIONS.read_text(encoding="utf-8"))) == 2
    # the same number spelled differently is the same participant, so Carol's
    # route back goes too
    assert web.post("/pair", json={"a": ALICE_SPELLED, "b": DAVE},
                    headers={"X-Proxy-Key": KEY}).status_code == 200
    recipe = importlib.reload(recipe)
    web = recipe.app.test_client()
    assert V.first(call(ALICE), "connect") == {"to": DAVE, "from": PROXY}
    assert V.verb_names(call(CAROL)) == ["answer", "play", "hangup"]
    assert len(json.loads(SESSIONS.read_text(encoding="utf-8"))) == 2

    # the schema says what the two fields mean
    defs = V.swml_schema()["$defs"]
    assert defs["ConnectDeviceSingle"]["properties"]["from"]["description"] == \
        "The caller ID to use when dialing the number."
    # send_sms is a Calling method, so a messaging document may not use it
    assert "send_sms" not in V.MESSAGING_METHODS, V.MESSAGING_METHODS
    assert "reply" in V.MESSAGING_METHODS, V.MESSAGING_METHODS

    # the payloads the handlers read carry every field the spec requires
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for hook, sample, key in (
            ("subpackage_callingWebhooks.inbound_call_webhook", inbound_call(ALICE), "call"),
            ("subpackage_messagingWebhooks.inbound_message_webhook", inbound_text(ALICE, TEXT),
             "message")):
        op = spec["webhooks"][hook]["post"]
        inner = deref(deref(list(op["requestBody"]["content"].values())[0]["schema"])
                      ["properties"][key])
        assert set(inner["required"]) <= set(sample[key]), (hook, inner["required"])
        assert {"from", "to"} <= set(inner["required"]), inner["required"]

    # nobody without the credentials reads or routes
    assert web.post("/call", json=inbound_call(ALICE)).status_code == 401
    assert web.post("/message", json=inbound_text(ALICE, TEXT)).status_code == 401

    node = V.node_surface(HERE, ALICE, BOB, STRANGER, TEXT, CAROL, ALICE_SPELLED, DAVE,
                          env={"SWML_BASIC_AUTH_USER": USER, "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                               "PROXY_NUMBER": PROXY, "PROXY_ADMIN_KEY": KEY})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["pair"] == {"noKey": 403, "wrongKey": 403, "withKey": 200}, node["pair"]
        for who, them in (("alice", BOB), ("bob", ALICE)):
            V.validate_swml(node["call"][who])
            assert V.first(node["call"][who], "connect") == {"to": them, "from": PROXY}
            V.assert_messaging_document(node["text"][who])
            assert V.first(node["text"][who], "reply") == {"to": them, "from": PROXY,
                                                           "body": TEXT}
        V.validate_swml(node["call"]["stranger"])
        assert V.verb_names(node["call"]["stranger"]) == ["answer", "play", "hangup"]
        assert node["text"]["stranger"]["sections"]["main"] == []
        assert node["unauthorized"] == {"call": 401, "message": 401}, node
        repaired = node["repaired"]
        assert V.first(repaired["alice"], "connect") == {"to": CAROL, "from": PROXY}
        assert V.first(repaired["carol"], "connect") == {"to": ALICE, "from": PROXY}
        assert V.verb_names(repaired["bob"]) == ["answer", "play", "hangup"]
        assert repaired["bobText"]["sections"]["main"] == []
        assert V.first(node["respelled"]["alice"], "connect") == {"to": DAVE, "from": PROXY}
        assert V.verb_names(node["respelled"]["carol"]) == ["answer", "play", "hangup"]
        ts_note = ("typescript pairs behind the same key, renders the same six documents, "
                   "and returns the same 401s")

    print(f"ok: pairing needs the key and writes two sessions; after a reload a call "
          f"from either party is connect to the other from {PROXY}, a stranger hears "
          f"the number is not active and is hung up on; a text from either party is "
          f"reply to the other from {PROXY} and a stranger's text is an empty "
          f"document; every document validates and both webhooks refuse an "
          f"unauthenticated POST; re-pairing Alice with Carol leaves Bob a stranger; "
          f"{ts_note}")


if __name__ == "__main__":
    main()
