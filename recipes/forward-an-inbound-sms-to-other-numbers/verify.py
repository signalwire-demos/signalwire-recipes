"""Prove the claim without a network.

Claim: a text arriving on your number is sent on to each recipient on a list,
prefixed with the sender's number and from the number that received it, and the
sender gets no reply. The method is `reply` with an explicit `to`, which is
what the Messaging SWML reference documents for forwarding.

Proof: the handler is driven with payloads shaped like the spec's inbound
message webhook. Every document is checked against the documented Messaging
method set rather than the bundled schema, which is the Calling one and would
accept the wrong verb. A customer's text renders one `reply` per recipient with
`to`, `from` and the prefixed body; the sender, the receiving line and a
repeated entry are each left out; a body at the platform's limit is truncated
so the prefix fits; a STOP renders nothing. A payload missing `from` or `to` is
a 400 and an unauthenticated post is a 401. The TypeScript surface does the
same. Expected values live here.
"""
import base64
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

USER, PASSWORD = "recipes", "pw"
LINE, CUSTOMER = "+15550001111", "+14155550123"
TEAM = ["+15550100001", "+15550100002"]
# the configured list carries a repeat and the receiving line, both of which
# the handler has to drop
FORWARD_TO = [TEAM[0], TEAM[1], TEAM[0], LINE]
os.environ.update({"SWML_BASIC_AUTH_USER": USER, "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                   "FORWARD_TO": ",".join(FORWARD_TO)})

import verifylib as V  # noqa: E402

TEXT = "Is my bike ready?"
MAX_BODY = 1600
LONG = "x" * MAX_BODY
PREFIX = f"{CUSTOMER}: "
TRUNCATED = PREFIX + "x" * (MAX_BODY - len(PREFIX))
PAIR = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
AUTH = {"Authorization": f"Basic {PAIR}"}


def replies(to_numbers, body, sender=CUSTOMER):
    return [{"reply": {"to": t, "from": LINE, "body": f"{sender}: {body}"}}
            for t in to_numbers]


# (sender, body) -> the exact steps, both surfaces
CASES = [
    ((CUSTOMER, TEXT), replies(TEAM, TEXT)),
    # a recipient texting the line is not sent their own message
    ((TEAM[0], "On my way"), replies([TEAM[1]], "On my way", sender=TEAM[0])),
    # an opt-out is for you, not for the team, punctuation and all
    ((CUSTOMER, " STOP. "), []),
    # the prefix eats into the platform's 1600 character body
    ((CUSTOMER, LONG), [{"reply": {"to": t, "from": LINE, "body": TRUNCATED}}
                        for t in TEAM]),
    # a media-only MMS forwards the prefix and nothing else
    ((CUSTOMER, ""), replies(TEAM, "")),
]


def inbound(sender, to, body):
    """The documented inbound-message payload."""
    message = {"message_id": "m-1", "project_id": "proj-1234", "space_id": "sp-1",
               "direction": "inbound", "type": "sms", "from": sender, "to": to,
               "body": body, "media": [], "segments": 1,
               "timestamp": "2026-09-05T09:00:00Z"}
    return {"message": message, "vars": {}, "params": {}}


def check(doc, want, label):
    # the bundled schema is the Calling one: it refuses `reply` and accepts
    # `send_sms`, so a messaging document is checked against the method set
    V.assert_messaging_document(doc)
    assert doc["sections"]["main"] == want, (label, doc["sections"]["main"])
    assert len(TRUNCATED) == MAX_BODY, len(TRUNCATED)


def main():
    V.sdk_banner()
    import app as recipe

    web = recipe.app.test_client()
    for (sender, body), want in CASES:
        r = web.post("/inbound", json=inbound(sender, LINE, body), headers=AUTH)
        assert r.status_code == 200, (sender, body[:20], r.status_code)
        check(r.get_json(), want, ("python", sender, body[:20]))

    # the spec: the payload carries every required field, from and to among them
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]
    op = spec["webhooks"]["subpackage_messagingWebhooks.inbound_message_webhook"]["post"]
    sch = list(op["requestBody"]["content"].values())[0]["schema"]
    while "$ref" in sch:
        sch = schemas[sch["$ref"].split("/")[-1]]
    msg = sch["properties"]["message"]
    while "$ref" in msg:
        msg = schemas[msg["$ref"].split("/")[-1]]
    sample = inbound(CUSTOMER, LINE, TEXT)["message"]
    assert set(msg["required"]) <= set(sample), msg["required"]
    assert {"from", "to", "body"} <= set(msg["required"]), msg["required"]
    # send_sms is a Calling method, so it is not in the set this recipe may use
    assert "send_sms" not in V.MESSAGING_METHODS, V.MESSAGING_METHODS
    assert {"reply", "receive"} <= V.MESSAGING_METHODS, V.MESSAGING_METHODS

    # a payload the webhook schema would not have sent
    short = {"message": {"body": "hi"}, "vars": {}, "params": {}}
    assert web.post("/inbound", json=short, headers=AUTH).status_code == 400
    # nobody without the credentials reads or forwards
    assert web.post("/inbound", json=inbound(CUSTOMER, LINE, TEXT)).status_code == 401

    cases = json.dumps([{"from": s, "to": LINE, "body": b} for (s, b), _ in CASES])
    node = V.node_surface(HERE, cases, env={"SWML_BASIC_AUTH_USER": USER,
                                            "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
                                            "FORWARD_TO": ",".join(FORWARD_TO)})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["results"]) == len(CASES), node
        for ((sender, body), want), doc in zip(CASES, node["results"]):
            check(doc, want, ("typescript", sender, body[:20]))
        assert node["unauthorized"] == 401, node
        assert node["incomplete"] == 400, node
        ts_note = "typescript renders the same five documents and the same 401 and 400"

    print(f"ok: a customer's text becomes {len(TEAM)} reply methods to the team from "
          f"{LINE}, each with an explicit to and the sender prefixed; the sender, the "
          f"receiving line and a repeated entry are dropped; a 1600 character body is "
          f"truncated to fit the prefix; STOP with punctuation forwards nothing; an "
          f"incomplete payload is 400 and an unauthenticated post is 401; {ts_note}")


if __name__ == "__main__":
    main()
