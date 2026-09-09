"""Prove the claim without a network.

Claim: one PATCH to the documented messaging path with `body: ""` redacts a
sent message's body, and the empty string is the only value the spec allows.

Proof: with the HTTP layer replaced by a recorder, `redact` makes exactly one
PATCH to the documented path for the id with the body `{"body": ""}`. The spec
marks `body` required and its description says it must be an empty string.
The operation's description says the call clears the body. It puts queued and
initiated on the refused side and delivered, undelivered and failed on the
eligible side. It says the original cannot be recovered. The 200 response
schema carries the message fields the README names. Expected values live here,
not in app.py.
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
})

import verifylib as V  # noqa: E402

TEMPLATE = "/api/messaging/messages/{message_id}"
MID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
PATH = TEMPLATE.replace("{message_id}", MID)


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.http = rec
    recipe.redact(MID)
    assert len(rec.calls) == 1, rec.calls
    (call,) = rec.calls
    assert (call["method"], call["path"]) == ("PATCH", PATH), call
    assert call["body"] == {"body": ""}, call
    V.assert_documented("rest", "PATCH", PATH, call["body"])

    # the spec's own words: body is required, and only "" is accepted
    spec = V.spec("rest")
    op = spec["paths"][TEMPLATE]["patch"]
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert schema["required"] == ["body"], schema.get("required")
    assert "empty string" in schema["properties"]["body"]["description"]
    desc = " ".join(op.get("description", "").split())
    # the meaning, and which states are on which side of the line
    assert "clears the message body" in desc, desc[:200]
    assert "(`queued` or `initiated`) cannot be redacted" in desc, desc
    assert "`delivered`, `undelivered`, or `failed` are eligible" in desc, desc
    assert "cannot be recovered" in desc, desc
    resp = op["responses"]["200"]["content"]["application/json"]["schema"]
    resp = spec["components"]["schemas"][resp["$ref"].split("/")[-1]] if "$ref" in resp else resp
    assert {"id", "body", "status", "direction", "from", "to", "created_at"} <= set(resp["properties"])

    print(f"ok: PATCH {PATH} with {{\"body\": \"\"}}. The spec requires body and allows "
          f"only the empty string. It says the call clears the body. Queued and initiated "
          f"are refused; delivered, undelivered and failed are eligible.")


if __name__ == "__main__":
    main()
