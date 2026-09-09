"""Prove the claim without a network.

Claim: the gate refuses, with 403 and before any route runs, a request whose
signature header does not match hex(HMAC(signing_key, url + raw_body)). The
SHA-256 header decides when present; otherwise the SHA-1 one does.

Proof: drive the Flask app with its test client and a signing key the verifier
owns. The gate serves a body signed with SHA-1 over url + body, and one signed
with SHA-256 alone. It refuses a valid SHA-1 beside an empty or wrong SHA-256,
because presence of the SHA-256 header selects it. It refuses a body altered by
one byte and a signature made with another key. It refuses a signature over
url + newline + body, one over the URL without its query string, a header that
is not hex, and a request with no header. Each refusal is a 403. It serves the
same valid request twice, which is the replay exposure the README names. The
served response is a SWML document that validates. Expected values live here,
not in app.py.
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
KEY = "PSK_verifier_only_not_a_real_key"
URL = "https://hooks.example.com/webhook"
os.environ.update({"SIGNALWIRE_SIGNING_KEY": KEY, "WEBHOOK_URL": URL})

import verifylib as V  # noqa: E402

BODY = json.dumps({"call": {"call_id": "c1", "to": "+15550001111", "from": "+15550002222"},
                   "vars": {}, "envs": {}, "params": {}}).encode()


def sign(key, url, body, digest):
    return hmac.new(key.encode(), url.encode() + body, digest).hexdigest()


def main():
    V.sdk_banner()
    import app as recipe

    client = recipe.app.test_client()

    def post(headers, body=BODY, path="/webhook"):
        return client.post(path, data=body, headers={"Content-Type": "application/json", **headers})

    # a correctly signed request is served, and the answer is SWML
    sha1 = sign(KEY, URL, BODY, hashlib.sha1)
    sha256 = sign(KEY, URL, BODY, hashlib.sha256)
    r = post({"X-Signalwire-Signature": sha1})
    assert r.status_code == 200, (r.status_code, r.data[:100])
    doc = r.get_json()
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "play", "hangup"], V.verb_names(doc)
    assert post({"X-Signalwire-SHA256-Signature": sha256}).status_code == 200
    assert post({"X-Signalwire-SHA256-Signature": sha256, "X-Signalwire-Signature": "junk"}).status_code == 200, \
        "the SHA-256 header should decide when both are present"
    for bad256 in ("", sign("other", URL, BODY, hashlib.sha256)):
        r = post({"X-Signalwire-SHA256-Signature": bad256, "X-Signalwire-Signature": sha1})
        assert r.status_code == 403, ("a bad SHA-256 beside a valid SHA-1 must not pass", repr(bad256), r.status_code)

    # every way a request can fail to be SignalWire's
    refused = {
        "no header": post({}),
        "altered body": post({"X-Signalwire-Signature": sha1}, body=BODY[:-1] + b" "),
        "another key": post({"X-Signalwire-Signature": sign("other", URL, BODY, hashlib.sha1)}),
        "a separator": post({"X-Signalwire-Signature": sign(KEY, URL + "\n", BODY, hashlib.sha1)}),
        "wrong sha256": post({"X-Signalwire-SHA256-Signature": sign("other", URL, BODY, hashlib.sha256)}),
        "empty header": post({"X-Signalwire-Signature": ""}),
        "not hex": post({"X-Signalwire-Signature": "zz" * 20}),
        "not ascii": post({"X-Signalwire-Signature": "caf\u00e9" * 10}),
        "not hex sha256": post({"X-Signalwire-SHA256-Signature": "nope", "X-Signalwire-Signature": sha1}),
    }
    for why, resp in refused.items():
        assert resp.status_code == 403, (why, resp.status_code, resp.data[:80])

    # the query string is part of the signed URL
    with_query = sign(KEY, URL + "?tenant=ridgeline", BODY, hashlib.sha1)
    assert post({"X-Signalwire-Signature": with_query}, path="/webhook?tenant=ridgeline").status_code == 200
    assert post({"X-Signalwire-Signature": sha1}, path="/webhook?tenant=ridgeline").status_code == 403, \
        "a signature over the bare URL must not pass for a request with a query"

    # the gate runs before routing: an unknown path is still 403, not 404, and
    # a signature valid for the webhook URL does not open another path (sol r3)
    assert post({}, path="/nothing-here").status_code == 403
    assert post({"X-Signalwire-Signature": sha1}, path="/nothing-here").status_code == 403, \
        "a valid signature for /webhook must not pass the gate at another path"

    # a configured query string is refused at startup, in a fresh interpreter
    import subprocess
    env = dict(os.environ, WEBHOOK_URL=URL + "?tenant=ridgeline")
    proc = subprocess.run([sys.executable, "-c", "import app"], cwd=HERE / "python",
                          env=env, capture_output=True, text=True)
    assert proc.returncode != 0 and "must not carry a query string" in proc.stderr, \
        (proc.returncode, proc.stderr[-300:])

    # what the gate does not do: the same valid request twice is served twice
    assert [post({"X-Signalwire-Signature": sha1}).status_code for _ in range(2)] == [200, 200], \
        "the gate has no replay protection, and the README says so"

    # the pure function agrees with the app, so you can call it outside Flask
    assert recipe.verify({"X-Signalwire-Signature": sha1}, URL, BODY) is True
    assert recipe.verify({"X-Signalwire-Signature": sha1}, URL, BODY[:-1]) is False
    assert recipe.verify({}, URL, BODY) is False

    print(f"ok: SHA-1 and SHA-256 signatures over url+body are served; no header, altered "
          f"body, another key, a separator, a stale query and an unknown path are all 403; "
          f"the reply is answer, play, hangup")


if __name__ == "__main__":
    main()
