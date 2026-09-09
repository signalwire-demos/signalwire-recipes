"""Prove the claim without a network.

Claim: a PubSub token grants `read` or `write` on named channels for a number
of minutes, and your server mints one per member with the role your sign-in
decided. The browser never holds the project API token.

Proof: with the HTTP layer replaced by a recorder, `reader_token` and
`publisher_token` each make one POST to the documented PubSub tokens path. The
reader body is exactly `ttl`, `member_id`, a channel with `read` true and
`write` false, and a `state`; the publisher body has `write` true. The spec
requires exactly `ttl` and `channels`, bounds `ttl` at 1 to 43,200, documents
`member_id` and `state`, and answers with `token`. The Flask route hands back
the minted token and the channel name and nothing else, refuses a request
without a member id, and never includes the API token. Expected values live
here, not in app.py.
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
    "CHANNEL": "workshop-board",
    "TOKEN_TTL_MINUTES": "60",
    "BOARD_KEY": "board-verifier-key",
})

import verifylib as V  # noqa: E402

PATH = "/api/pubsub/tokens"


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"token": "pubsub-reader-verifier"}, {"token": "pubsub-writer-verifier"}])
    recipe.client.pubsub._http = rec
    reader = recipe.reader_token("dana")
    writer = recipe.publisher_token("board-1")
    assert (reader, writer) == ({"token": "pubsub-reader-verifier"}, {"token": "pubsub-writer-verifier"})
    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", PATH), ("POST", PATH)], rec.calls
    r_body, w_body = (c["body"] for c in rec.calls)
    assert r_body == {"ttl": 60, "member_id": "dana",
                      "channels": {"workshop-board": {"read": True, "write": False}},
                      "state": {"role": "reader"}}, r_body
    assert w_body == {"ttl": 60, "member_id": "board-1",
                      "channels": {"workshop-board": {"read": True, "write": True}},
                      "state": {"role": "publisher"}}, w_body

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", PATH, r_body)
    op = spec["paths"][PATH]["post"]
    schema = deref(spec, op["requestBody"]["content"]["application/json"]["schema"])
    assert set(schema["required"]) == {"ttl", "channels"}, schema["required"]
    ttl = deref(spec, schema["properties"]["ttl"])
    assert "43,200" in ttl["description"] and "minutes" in ttl["description"], ttl["description"]
    channels = deref(spec, schema["properties"]["channels"])
    assert "`read` and/or `write`" in channels["description"], channels["description"]
    assert {"member_id", "state"} <= set(schema["properties"]), sorted(schema["properties"])
    resp = deref(spec, op["responses"]["200"]["content"]["application/json"]["schema"])
    assert "token" in resp["properties"], sorted(resp["properties"])

    # the route: role from your sign-in, token and channel back, nothing else
    rec2 = V.Recorder(responses=[{"token": "t-reader"}, {"token": "t-writer"}])
    recipe.client.pubsub._http = rec2
    client = recipe.app.test_client()
    r = client.post("/pubsub/token", json={"member_id": "dana"})
    assert r.status_code == 200 and r.get_json() == {"token": "t-reader", "channel": "workshop-board"}, r.get_json()
    # a browser may ask to publish; without the board's key the server refuses
    # and mints nothing
    r = client.post("/pubsub/token", json={"member_id": "dana", "role": "publisher"})
    assert r.status_code == 403, r.status_code
    r = client.post("/pubsub/token", json={"member_id": "dana", "role": "publisher"},
                    headers={"X-Board-Key": "wrong"})
    assert r.status_code == 403, r.status_code
    assert len(rec2.calls) == 1, "a refused publisher request must mint nothing"
    r = client.post("/pubsub/token", json={"member_id": "board-1", "role": "publisher"},
                    headers={"X-Board-Key": "board-verifier-key"})
    assert r.get_json() == {"token": "t-writer", "channel": "workshop-board"}, r.get_json()
    # both route bodies in full: one per member, with that member's id
    assert [c["body"] for c in rec2.calls] == [
        {"ttl": 60, "member_id": "dana",
         "channels": {"workshop-board": {"read": True, "write": False}}, "state": {"role": "reader"}},
        {"ttl": 60, "member_id": "board-1",
         "channels": {"workshop-board": {"read": True, "write": True}}, "state": {"role": "publisher"}},
    ], [c["body"] for c in rec2.calls]
    assert client.post("/pubsub/token", json={}).status_code == 400
    assert len(rec2.calls) == 2, "a request without a member id must mint nothing"
    for c in rec2.calls:
        assert "PT-test" not in str(c)

    print(f"ok: reader and publisher tokens POST {PATH} with ttl 60, the member, per-channel read/write "
          f"and a state; the spec requires ttl and channels and bounds ttl at 1 to 43,200 minutes; the "
          f"route returns only the token and the channel")


if __name__ == "__main__":
    main()
