"""Prove the claim without a network.

Claim: a message is accepted, then delivered or failed; the status callback, not
the send response, is the truth.

Proof: (1) swap the REST client's HTTP layer for a recorder and assert the send
is a POST to the documented Compatibility Messages path with the documented
fields, checked against the OpenAPI spec in tools/openapi/compat.json;
(2) drive the status webhook with Flask's test client and assert that a
duplicate terminal callback triggers the side effect exactly once, and that
'queued'/'sent' trigger it never.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SIGNALWIRE_PHONE_NUMBER": "+15550001111", "PUBLIC_URL": "https://recipes.example.test",
})
sys.path.insert(0, str(HERE / "python"))

import signalwire  # noqa: E402
import app as recipe  # noqa: E402


class Recorder:
    def __init__(self):
        self.calls = []

    def post(self, path, body=None, params=None):
        self.calls.append(("POST", path, body))
        return {"sid": "SM123", "status": "queued"}


def main():
    print(f"sdk {signalwire.__version__} at {signalwire.__file__}")
    rec = Recorder()
    recipe.client.compat.messages._http = rec

    sid = recipe.send("+15552223333", "Your table is ready.")
    assert sid == "SM123"
    (method, path, body), = rec.calls
    assert method == "POST"
    assert path == "/api/laml/2010-04-01/Accounts/proj-1234/Messages", path

    spec = json.loads((ROOT / "tools" / "openapi" / "compat.json").read_text(encoding="utf-8"))
    op = spec["paths"]["/Accounts/{AccountSid}/Messages"]["post"]
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    allowed = set(schema["properties"])
    assert set(body) <= allowed, set(body) - allowed
    for req in schema.get("required", []):
        assert req in body, f"missing required field {req}"
    assert body["StatusCallback"] == "https://recipes.example.test/sms-status"
    assert body["From"] == "+15550001111" and body["To"] == "+15552223333"

    # The webhook is the truth, and it is idempotent.
    fired = []
    recipe.on_terminal = lambda sid, status, err: fired.append((sid, status, err))
    c = recipe.app.test_client()
    post = lambda **f: c.post("/sms-status", data=f)  # noqa: E731
    assert post(MessageSid="SM123", MessageStatus="queued").status_code == 204
    assert post(MessageSid="SM123", MessageStatus="sent").status_code == 204
    assert fired == [], fired
    post(MessageSid="SM123", MessageStatus="delivered")
    post(MessageSid="SM123", MessageStatus="delivered")  # carrier retry
    assert fired == [("SM123", "delivered", None)], fired
    post(MessageSid="SM124", MessageStatus="failed", ErrorCode="30007")
    assert fired[-1] == ("SM124", "failed", "30007"), fired

    print(f"ok: POST {path} with {sorted(body)}; duplicate 'delivered' fired once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
