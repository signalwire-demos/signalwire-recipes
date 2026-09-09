"""Prove the claim without a network.

Claim: your webhook handler records a STOP from the inbound message webhook
and confirms it with a `reply` document. Every later send checks that
record before it makes a request, so a refused send is never a request. The
handler accepts the webhook only with SignalWire's signature over it.

Proof: drive the Flask app with its test client. A webhook payload shaped
like the spec's inbound message webhook, with every required field, carries a
body of "STOP". The answer is a SWML document that validates and holds exactly
one `reply` from the receiving number back to the sender with the
confirmation text. With the HTTP layer replaced by a recorder, `send` to that
number raises `OptedOut` and records nothing, and `POST /send` answers 403.
`send` to another number makes one POST to the documented messages path with
exactly the expected body, and `POST /send` answers 202. "START" clears the
record and `send` works again. A body that is not a keyword answers with an
empty document and records nothing. Expected values live here, not in app.py.
"""
import hashlib
import hmac
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
    "SMS_FROM": "+15550001111",
    "SIGNALWIRE_SIGNING_KEY": "PSK_verifier_only",
    "INBOUND_URL": "https://hooks.example.com/inbound",
})

import verifylib as V  # noqa: E402

MESSAGES = "/api/messaging/messages"
OURS, CUSTOMER, OTHER = "+15550001111", "+15550002222", "+15550003333"
STOPPED = ("You are unsubscribed from Ridgeline Cycles messages. "
           "Reply START to opt back in.")
RESUMED = "You are opted back in to Ridgeline Cycles messages. Reply STOP at any time."


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def webhook(spec):
    """The spec's own schema for what SignalWire POSTs to a messaging webhook."""
    hook = spec["webhooks"]["subpackage_messagingWebhooks.inbound_message_webhook"]["post"]
    return deref(spec, hook["requestBody"]["content"]["application/json"]["schema"])


def payload(body, sender=CUSTOMER):
    return {"message": {"message_id": "5f0f3a2e-1111-4e7a-9f0d-1c2b3a4d5e6f",
                        "project_id": "proj-1234", "space_id": "space-1",
                        "direction": "inbound", "type": "sms", "from": sender, "to": OURS,
                        "body": body, "media": [], "segments": 1,
                        "timestamp": "2026-09-02T10:00:00Z"},
            "params": {}}


def main():
    V.sdk_banner()
    import app as recipe

    spec = V.spec("rest")
    hook = webhook(spec)
    # the fixture is shaped like the documented webhook: every required key at
    # both levels, and no key the spec does not know
    sample = payload("STOP")
    assert set(hook["required"]) <= set(sample), hook["required"]
    assert set(sample) <= set(hook["properties"]), sorted(set(sample) - set(hook["properties"]))
    message = deref(spec, hook["properties"]["message"])
    assert set(message["required"]) <= set(sample["message"]), message["required"]
    assert set(sample["message"]) <= set(message["properties"]), \
        sorted(set(sample["message"]) - set(message["properties"]))
    assert "inbound" in deref(spec, message["properties"]["direction"])["enum"]

    client = recipe.app.test_client()
    rec = V.Recorder(responses=[{"id": "msg-1", "status": "queued"}])
    recipe.http = rec

    def signed_post(body, sender=CUSTOMER, key="PSK_verifier_only", headers=None):
        raw = json.dumps(payload(body, sender)).encode()
        if headers is None:
            sig = hmac.new(key.encode(), b"https://hooks.example.com/inbound" + raw,
                           hashlib.sha1).hexdigest()
            headers = {"X-Signalwire-Signature": sig}
        return client.post("/inbound", data=raw,
                           headers={"Content-Type": "application/json", **headers})

    def post(body, sender=CUSTOMER):
        r = signed_post(body, sender)
        assert r.status_code == 200, (body, r.status_code, r.data[:100])
        doc = r.get_json()
        # the bundled schema is the Calling one: it refuses `reply` and accepts
        # `send_sms`, so a messaging document is checked against the method set
        V.assert_messaging_document(doc)
        return doc

    # only SignalWire may report a STOP or a START: no signature, or a forged
    # one, changes nothing
    recipe.OPT_OUTS[OTHER] = "2026-09-01T00:00:00+00:00"
    for headers in ({}, {"X-Signalwire-Signature": "not-a-signature"}):
        r = signed_post("START", OTHER, headers=headers)
        assert r.status_code == 403, (headers, r.status_code)
    assert signed_post("START", OTHER, key="attacker").status_code == 403
    assert OTHER in recipe.OPT_OUTS, "a forged START cleared a record"
    recipe.OPT_OUTS.pop(OTHER)

    # a plain message: empty document, nothing recorded
    doc = post("thanks, see you saturday")
    assert V.verb_names(doc) == [], doc
    assert CUSTOMER not in recipe.OPT_OUTS

    # STOP, with the casing and spacing a phone produces
    doc = post(" Stop ")
    assert V.verb_names(doc) == ["reply"], doc
    assert V.first(doc, "reply") == {"from": OURS, "to": CUSTOMER,
                                     "body": STOPPED}, V.first(doc, "reply")
    # send_sms is a Calling method, so a messaging document may not use it
    assert "send_sms" not in V.MESSAGING_METHODS, V.MESSAGING_METHODS
    assert CUSTOMER in recipe.OPT_OUTS

    # the record is checked before the request is built
    try:
        recipe.send(CUSTOMER, "Your bike is ready.")
    except recipe.OptedOut as e:
        assert CUSTOMER in str(e), str(e)
    else:
        raise AssertionError("send to an opted-out number did not raise")
    assert rec.calls == [], rec.calls
    r = client.post("/send", json={"to": CUSTOMER, "body": "Your bike is ready."})
    assert r.status_code == 403 and CUSTOMER in r.get_json()["reason"], (r.status_code, r.get_json())
    assert rec.calls == [], rec.calls

    # a number with no record sends, and the request is the documented one
    recipe.send(OTHER, "Your bike is ready.")
    assert len(rec.calls) == 1, rec.calls
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("POST", MESSAGES), call
    assert call["body"] == {"to": OTHER, "from": OURS, "body": "Your bike is ready."}, call
    V.assert_documented("rest", "POST", MESSAGES, call["body"])
    r = client.post("/send", json={"to": OTHER, "body": "See you Saturday."})
    assert r.status_code == 202 and r.get_json()["sent"] is True, (r.status_code, r.get_json())
    assert len(rec.calls) == 2 and rec.calls[1]["body"]["body"] == "See you Saturday.", rec.calls
    rec.calls.pop()

    # START clears the record and the next send goes out
    doc = post("START")
    assert V.first(doc, "reply") == {"from": OURS, "to": CUSTOMER,
                                     "body": RESUMED}, V.first(doc, "reply")
    assert CUSTOMER not in recipe.OPT_OUTS
    recipe.send(CUSTOMER, "Welcome back.")
    assert len(rec.calls) == 2 and rec.calls[1]["body"]["to"] == CUSTOMER, rec.calls

    # every keyword this handler honours, in three casings, is a whole word
    for word in ("stop", "stopall", "unsubscribe", "cancel", "end", "quit"):
        for variant in (word, word.upper(), word.capitalize()):
            post(variant, sender=OTHER)
            assert OTHER in recipe.OPT_OUTS, variant
            recipe.OPT_OUTS.pop(OTHER)
    post("please stop calling", sender=OTHER)
    assert OTHER not in recipe.OPT_OUTS, "a sentence containing stop is not a STOP"

    print(f"ok: an unsigned or forged START is 403 and changes nothing; STOP from {CUSTOMER} "
          f"answered with one reply confirmation and recorded; "
          f"send to it raised OptedOut with no request; send to {OTHER} made one POST "
          f"{MESSAGES}; START cleared the record")


if __name__ == "__main__":
    main()
