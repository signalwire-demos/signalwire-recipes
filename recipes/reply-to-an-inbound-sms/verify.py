"""Prove the claim without a network.

Claim: an inbound message hits your handler and a reply goes back on the same
number, with keyword branching and media download.

Proof: drive the webhook with the documented inbound-message payload and assert
the returned messaging SWML is a `reply` whose body follows the keyword; a
media-only MMS records the attachment URL and gets its own reply; STOP is
recorded. The YAML surface's inline switch covers the same keywords.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402


def payload(body=None, media=None, sender="+15552223333"):
    # Shape from docs: apis/rest/webhooks/inbound-message-webhook
    return {"message": {
        "message_id": "m1", "project_id": "p", "space_id": "s", "direction": "inbound",
        "type": "mms" if media else "sms", "from": sender, "to": "+15550001111",
        "body": body, "media": media or [], "segments": 1, "timestamp": "2026-08-25T00:00:00Z",
    }, "params": {}}


def main():
    import app as recipe
    c = recipe.app.test_client()

    def reply(**kw):
        doc = c.post("/sms", json=payload(**kw)).get_json()
        assert doc["version"] == "1.0.0"
        (step,) = doc["sections"]["main"]
        assert set(step) == {"reply"} and set(step["reply"]) == {"body"}, step
        return step["reply"]["body"]

    assert reply(body="HOURS ") == recipe.REPLIES["hours"]
    assert reply(body="help") == recipe.REPLIES["help"]
    assert reply(body="what?") == recipe.DEFAULT
    assert reply(body="Stop", sender="+15559998888") == recipe.REPLIES["stop"]
    assert "+15559998888" in recipe.opted_out
    media = [{"url": "https://media.example.test/a.jpg", "content_type": "image/jpeg", "size": 1234}]
    assert reply(body=None, media=media) == "Got your picture, thanks."
    assert recipe.received_media[-1]["url"] == media[0]["url"]

    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    (step,) = y["sections"]["main"]
    sw = step["reply"]["switch"]
    assert sw["variable"] == "message.body" and sw["transform"] == "lowercase_trim", sw
    assert set(sw["case"]) == set(recipe.REPLIES), sw["case"]
    assert sw["default"] == recipe.DEFAULT
    print(f"ok: reply bodies branch on {sorted(recipe.REPLIES)} + default; MMS media captured; STOP recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
