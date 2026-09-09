"""Prove the claim without a network.

Claim: a message status callback reporting `undelivered` or `failed` places
one call that speaks the message to the same recipient, once per message id,
and only when SignalWire signed the callback.

Proof: with the HTTP layer replaced by a recorder and the marker directory in a
temp directory, seven signed callbacks are posted. Exactly two dial requests
result, to the documented path with the documented SWML variant's params; each
inline document validates and speaks the body on one line, so a body carrying a
newline still passes the play url's pattern. The marker for a message id exists
before its dial goes out, which is what makes a repeated callback place
nothing. A callback with no id, no recipient, or a status the recipe does not
act on places nothing. An unsigned callback, a bad signature and an empty
SHA-256 header beside a valid SHA-1 are all 403, while a SHA-256 signature and
a query-tagged URL are accepted. A query carrying an encoded space is accepted
too, so the signature is over the raw query rather than a re-serialised one. A
dial whose response never arrives keeps its claim, so the same callback places
nothing afterwards. On the TypeScript surface that failure is a 500 rather than
an exit, and the request after it is served. The TypeScript surface does the
same as Python otherwise, and a tagged `STATUS_URL` is signed once on both.
Expected values live here.
"""
import hashlib
import hmac
import importlib
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

KEY, FROM = "signing-key-test", "+15550001111"
BASE = "https://recipes.example.test/message-status"
HANDLED = pathlib.Path(tempfile.mkdtemp()) / "handled"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com", "SIGNALWIRE_SIGNING_KEY": KEY,
    "VOICE_FROM": FROM, "STATUS_URL": BASE, "HANDLED_DIR": str(HANDLED),
})

import verifylib as V  # noqa: E402

CALLS = "/api/calling/calls"
TO = "+14155550123"
# a body a real notice carries: two lines, which the play url's pattern refuses
BODY = "Your bike is ready.\nPick up by 6pm."
LEAD = "We could not reach you by text. The message was: "
SPOKEN = LEAD + "Your bike is ready. Pick up by 6pm."
SECOND = "See you at nine."


def event(message_id, status, body=BODY, to=TO):
    """The documented message status callback payload."""
    return {"id": message_id, "project_id": "proj-1234", "status": status, "to": to,
            "from": "+15550002222", "body": body, "number_of_segments": 1,
            "timestamp": "2026-09-05T09:00:00Z", "error_code": None,
            "error_message": None}


EVENTS = [event("m-1", "undelivered"), event("m-1", "undelivered"),
          event("m-2", "delivered"), event("m-3", "failed", SECOND),
          event("m-4", "sent"), event(None, "failed"), event("m-5", "failed", to=None)]
ANSWERS = [{"called": True, "call_id": "call-1"},
           {"called": False, "reason": "already handled"},
           {"called": False, "reason": "delivered"},
           {"called": True, "call_id": "call-2"},
           {"called": False, "reason": "sent"},
           {"called": False, "reason": "no message id"},
           {"called": False, "reason": "no recipient"}]
SAID = [SPOKEN, LEAD + SECOND]


def sign(raw, digest=hashlib.sha1, query=""):
    url = BASE + (("?" + query) if query else "")
    return hmac.new(KEY.encode(), url.encode() + raw, digest).hexdigest()


def check_calls(calls, label):
    assert len(calls) == 2, (label, len(calls))
    spec = V.spec("rest")["components"]["schemas"]["Calling.CallCreateParamsSWML"]
    for call, said in zip(calls, SAID):
        assert (call["method"], call["path"]) == ("POST", CALLS), (label, call)
        assert call["body"]["command"] == "dial", (label, call["body"])
        params = call["body"]["params"]
        assert set(params) <= set(spec["properties"]), (label, set(params))
        assert set(spec["required"]) <= set(params), (label, spec["required"])
        assert (params["from"], params["to"], params["timeout"]) == (FROM, TO, 25), params
        doc = params["swml"]
        V.validate_swml(doc)
        assert V.verb_names(doc) == ["answer", "play", "hangup"], (label, doc)
        assert V.first(doc, "play")["url"] == f"say:{said}", (label, doc)
        assert "\n" not in V.first(doc, "play")["url"], (label, doc)


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"id": "call-1"}, {"id": "call-2"}])
    V.record_everything(recipe.client, rec)
    # the id must already be claimed by the time the dial goes out
    marks, original_post = [], rec.post

    def post_and_count(*args, **kwargs):
        marks.append(len(list(recipe.HANDLED_DIR.iterdir())))
        return original_post(*args, **kwargs)

    rec.post = post_and_count
    web = recipe.app.test_client()

    answers = []
    for ev in EVENTS:
        raw = json.dumps(ev).encode()
        r = web.post("/message-status", data=raw, content_type="application/json",
                     headers={"X-Signalwire-Signature": sign(raw)})
        assert r.status_code == 200, (r.status_code, r.data)
        answers.append(r.get_json())
    assert answers == ANSWERS, answers
    check_calls(rec.calls, "python")
    assert marks and all(n >= 1 for n in marks), marks

    # nothing unsigned spends anything, and the SHA-256 header decides when present
    raw = json.dumps(event("m-9", "failed")).encode()
    for headers in ({}, {"X-Signalwire-Signature": "00"},
                    {"X-Signalwire-SHA256-Signature": "",
                     "X-Signalwire-Signature": sign(raw)}):
        r = web.post("/message-status", data=raw, content_type="application/json",
                     headers=headers)
        assert r.status_code == 403, (headers, r.status_code)
    ok256 = web.post("/message-status", data=raw, content_type="application/json",
                     headers={"X-Signalwire-SHA256-Signature": sign(raw, hashlib.sha256)})
    assert ok256.status_code == 200, ok256.status_code
    # a query on the request is part of the URL the signature covers
    other = json.dumps(event("m-10", "failed")).encode()
    tagged = web.post("/message-status?token=abc", data=other,
                      content_type="application/json",
                      headers={"X-Signalwire-Signature": sign(other, query="token=abc")})
    assert tagged.status_code == 200, tagged.status_code
    # the two accepted callbacks each placed one call; the three refused did not
    assert len(rec.calls) == 4, len(rec.calls)

    # the signature covers the raw query, so an encoded space is not normalised
    first = json.dumps(EVENTS[0]).encode()
    enc = web.post("/message-status?tag=a%20b", data=first,
                   content_type="application/json",
                   headers={"X-Signalwire-Signature": sign(first, query="tag=a%20b")})
    assert enc.status_code == 200, enc.status_code
    assert enc.get_json() == {"called": False, "reason": "already handled"}, \
        enc.get_json()

    # a dial whose response never arrives keeps the claim: at most one call
    boom = event("m-11", "failed")

    def never_answers(*args, **kwargs):
        raise RuntimeError("the response never arrived")

    rec.post, raised = never_answers, None
    try:
        recipe.handle(boom)
    except Exception as exc:            # any failure leaves the outcome unknown
        raised = exc
    assert raised is not None, "the dial should have raised"
    rec.post = post_and_count
    again = recipe.handle(boom)
    assert again == {"called": False, "reason": "already handled"}, again
    assert len(rec.calls) == 4, len(rec.calls)

    # a STATUS_URL that carries its own query is signed once, not twice
    assert recipe.signed_url("token=abc") == BASE + "?token=abc"
    os.environ["STATUS_URL"] = BASE + "?token=abc"
    tagged_recipe = importlib.reload(recipe)
    assert tagged_recipe.signed_url("token=abc") == BASE + "?token=abc", \
        tagged_recipe.signed_url("token=abc")
    os.environ["STATUS_URL"] = BASE
    importlib.reload(recipe)

    # the spec: the payload the handler reads, and what it says about callbacks
    spec = V.spec("rest")
    op = spec["webhooks"]["subpackage_messagingWebhooks.message_status_callback"]["post"]
    sch = list(op["requestBody"]["content"].values())[0]["schema"]
    schemas = spec["components"]["schemas"]
    while "$ref" in sch:
        sch = schemas[sch["$ref"].split("/")[-1]]
    assert {"id", "status", "to", "body"} <= set(sch["required"]), sch["required"]
    assert set(sch["required"]) <= set(EVENTS[0]), sch["required"]
    status = sch["properties"]["status"]
    while "$ref" in status:
        status = schemas[status["$ref"].split("/")[-1]]
    assert {"undelivered", "failed", "delivered", "sent"} <= set(status["enum"]), \
        status["enum"]
    assert "advisory, best-effort notifications" in op.get("description", "")

    env = {"SIGNALWIRE_SIGNING_KEY": KEY, "VOICE_FROM": FROM, "STATUS_URL": BASE}
    node = V.node_surface(HERE, json.dumps(EVENTS), env=env)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["answers"] == ANSWERS, node["answers"]
        check_calls(node["captured"], "typescript")
        assert node["marksAtDial"] and all(n >= 1 for n in node["marksAtDial"]), node
        refusals = (node["unsigned"], node["badSig"], node["emptySha256"])
        assert refusals == (403, 403, 403), refusals
        assert (node["sha256"], node["tagged"]) == (200, 200), node
        assert node["encoded"] == 200, node["encoded"]
        # node:http does not await its listener, so a failed dial that escaped
        # would end the process rather than answer. It is a 500, and the next
        # request is served and finds the claim.
        assert node["failed"] == 500, node["failed"]
        assert node["alive"] == 200, node["alive"]
        assert node["afterFailure"] == {"called": False,
                                        "reason": "already handled"}, node
        assert node["signedUrlTagged"] == BASE + "?token=abc", node["signedUrlTagged"]
        tagged_node = V.node_surface(HERE, "[]", env={**env, "STATUS_URL": BASE + "?t=1"})
        assert tagged_node["signedUrlTagged"] == BASE + "?token=abc", tagged_node
        ts_note = ("typescript places the same two calls, claims before it dials, "
                   "signs a tagged URL once, and answers a failed dial with a 500 "
                   "that keeps the claim and the server")

    print(f"ok: undelivered and failed each place one dial to {TO} with inline SWML "
          f"whose spoken line is single line even for a two line body; a repeat, a "
          f"delivered, a sent, an event with no id and one with no recipient place "
          f"nothing; the id is claimed before the dial; unsigned, bad and empty "
          f"SHA-256 signatures are 403 while SHA-256 and a tagged query are accepted; "
          f"{ts_note}")


if __name__ == "__main__":
    main()
