"""Prove the claim without a network.

Claim: `calling.transcribe` starts transcribing a live call in the background
by `control_id`, and `calling.transcribe.stop` ends it. SignalWire may then
send the documented transcript callback to your `status_url`, whose
`params.text` holds the text when there is any.

Proof: the HTTP layer is a recorder. `start` and `stop` each make one POST to
the documented calling path whose body equals one expected object. The spec's
variants require exactly `control_id`. The Flask app receives two callbacks
shaped like the spec's transcribe status callback, every required field
present and nothing undocumented. One is completed with text and one is failed
without it. Each is signed the way SignalWire signs a webhook; an unsigned or
forged one is refused and stores nothing. The app stores each signed one under
its call id. `GET /transcripts/<call_id>` returns it to a caller with the read
token and refuses one without, and an unknown call reads as pending. Expected
values live here, not in app.py.
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
    "TRANSCRIBE_STATUS_URL": "https://example.com/transcripts",
    "SIGNALWIRE_SIGNING_KEY": "PSK_verifier_only",
    "READ_TOKEN": "read-verifier-only",
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
CALL = "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f"
FAILED = "0a1b2c3d-1111-4e7a-9f0d-1c2b3a4d5e6f"
TEXT = "Hi, this is Ridgeline Cycles. Your bike is ready for pickup any time before six."


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def variant(spec, command):
    for v in spec["components"]["schemas"]["Calling.CallRequest"]["oneOf"]:
        v = deref(spec, v)
        if command in (deref(spec, v["properties"]["command"]).get("enum") or []):
            return v.get("required", []), deref(spec, v["properties"]["params"])
    raise AssertionError(f"{command} is not a documented call command")


def callback(event_type, call_id, **extra):
    return {"event_type": event_type, "timestamp": 1788350400.5, "project_id": "proj-1234",
            "space_id": "space-1",
            "params": {"id": "t-1", "call_id": call_id, "segment_id": "seg-1", **extra}}


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.start(CALL)
    recipe.stop(CALL)
    assert [(c["method"], c["path"]) for c in rec.calls] == [("POST", PATH), ("POST", PATH)], rec.calls
    start, stop = rec.calls
    assert start["body"] == {"command": "calling.transcribe", "id": CALL,
                             "params": {"control_id": "call-transcript",
                                        "status_url": "https://example.com/transcripts"}}, start
    assert stop["body"] == {"command": "calling.transcribe.stop", "id": CALL,
                            "params": {"control_id": "call-transcript"}}, stop

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", PATH, None)
    for call, command in ((start, "calling.transcribe"), (stop, "calling.transcribe.stop")):
        required, params = variant(spec, command)
        assert set(required) == {"command", "id", "params"}, (command, required)
        assert params["required"] == ["control_id"], (command, params.get("required"))
        assert set(call["body"]["params"]) <= set(params["properties"]), \
            (command, sorted(set(call["body"]["params"]) - set(params["properties"])))

    # the callback, as the spec documents it
    hook = spec["webhooks"]["subpackage_callingWebhooks.transcribe_status_callback"]["post"]
    schema = deref(spec, hook["requestBody"]["content"]["application/json"]["schema"])
    types = deref(spec, schema["properties"]["event_type"])["enum"]
    assert set(types) == {"calling.transcript.completed", "calling.transcript.failed"}, types
    p_schema = deref(spec, schema["properties"]["params"])
    assert "Omitted when there is no transcribed text" in \
        deref(spec, p_schema["properties"]["text"])["description"]
    done = callback("calling.transcript.completed", CALL, text=TEXT)
    failed = callback("calling.transcript.failed", FAILED)
    for e in (done, failed):
        assert set(schema["required"]) <= set(e), sorted(set(schema["required"]) - set(e))
        assert set(e) <= set(schema["properties"]), sorted(set(e) - set(schema["properties"]))
        assert set(p_schema.get("required", [])) <= set(e["params"]), p_schema.get("required")
        assert set(e["params"]) <= set(p_schema["properties"]), sorted(e["params"])

    client = recipe.app.test_client()
    READ = {"Authorization": "Bearer read-verifier-only"}

    def post(event, key="PSK_verifier_only", headers=None):
        raw = json.dumps(event).encode()
        if headers is None:
            sig = hmac.new(key.encode(), b"https://example.com/transcripts" + raw,
                           hashlib.sha1).hexdigest()
            headers = {"X-Signalwire-Signature": sig}
        return client.post("/transcripts", data=raw,
                           headers={"Content-Type": "application/json", **headers})

    assert client.get(f"/transcripts/{CALL}").status_code == 401, "a read without the token"
    assert client.get(f"/transcripts/{CALL}", headers=READ).get_json() == {"status": "pending", "text": None}
    # only SignalWire's signature gets a callback stored
    assert post(done, headers={}).status_code == 403
    assert post(done, key="attacker").status_code == 403
    assert recipe.TRANSCRIPTS == {}, "a refused callback must store nothing"
    # the header that is present decides: SHA-256 alone is accepted, and a
    # valid SHA-1 beside an empty SHA-256 header is refused (docs: both
    # headers are documented; the check never falls back to the other one)
    raw = json.dumps(done).encode()
    url = b"https://example.com/transcripts"
    sha256 = hmac.new(b"PSK_verifier_only", url + raw, hashlib.sha256).hexdigest()
    sha1 = hmac.new(b"PSK_verifier_only", url + raw, hashlib.sha1).hexdigest()
    hdr = {"Content-Type": "application/json"}
    r = client.post("/transcripts", data=raw,
                    headers={**hdr, "X-Signalwire-Signature": sha1, "X-Signalwire-SHA256-Signature": ""})
    assert r.status_code == 403, r.status_code
    assert recipe.TRANSCRIPTS == {}
    r = client.post("/transcripts", data=raw, headers={**hdr, "X-Signalwire-SHA256-Signature": sha256})
    assert r.status_code == 204, r.status_code
    recipe.TRANSCRIPTS.clear()
    # a configured URL that already carries a query is signed as that URL, once;
    # the first version appended the request's query again and refused the
    # genuine callback (codex, wave 9 review)
    recipe.STATUS_URL = "https://example.com/transcripts?src=recipe"
    try:
        raw = json.dumps(done).encode()
        once = hmac.new(b"PSK_verifier_only", b"https://example.com/transcripts?src=recipe" + raw,
                        hashlib.sha1).hexdigest()
        twice = hmac.new(b"PSK_verifier_only",
                         b"https://example.com/transcripts?src=recipe?src=recipe" + raw,
                         hashlib.sha1).hexdigest()
        hdr = {"Content-Type": "application/json"}
        assert client.post("/transcripts?src=recipe", data=raw,
                           headers={**hdr, "X-Signalwire-Signature": twice}).status_code == 403
        assert client.post("/transcripts?src=recipe", data=raw,
                           headers={**hdr, "X-Signalwire-Signature": once}).status_code == 204
        recipe.TRANSCRIPTS.clear()  # the pending-state assertions below start clean
    finally:
        recipe.STATUS_URL = "https://example.com/transcripts"
    assert client.get(f"/transcripts/{CALL}", headers=READ).get_json()["status"] == "pending"
    for e in (done, failed):
        r = post(e)
        assert r.status_code == 204, (r.status_code, r.data[:80])
    assert client.get(f"/transcripts/{CALL}", headers=READ).get_json() == \
        {"status": "completed", "text": TEXT, "at": 1788350400.5}
    assert client.get(f"/transcripts/{FAILED}", headers=READ).get_json() == \
        {"status": "failed", "text": None, "at": 1788350400.5}

    print(f"ok: calling.transcribe and calling.transcribe.stop POST the expected bodies for "
          f"{CALL[:8]}...; a signed completed callback stores {len(TEXT)} characters of text and "
          f"a failed one stores none; unsigned ones are 403; reads need the bearer token")


if __name__ == "__main__":
    main()
