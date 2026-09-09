"""Prove the claim without a network.

Claim: several callers share one named audio conference, and members can be
muted, removed and listed over REST.

Proof: both surfaces validate against the SWML schema and name the same room,
so two calls running them are in one conference. The host and guest documents
differ only in who may start and end it. The REST controls make documented
Compatibility requests against the paths in tools/openapi/compat.json.
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
    "CONFERENCE_NAME": "standup",
    "PUBLIC_URL": "https://recipes.example.test",
})

import verifylib as V  # noqa: E402

ROOM = "standup"
CONF = "CF00000000000000000000000000000000"
CALL = "CA11111111111111111111111111111111"


def room_of(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "join_conference", "hangup"], (
        label, V.verb_names(doc))
    jc = V.first(doc, "join_conference")
    # `name` is the only required field, and it is the whole identity
    assert jc["name"] == ROOM, (label, jc)
    assert 0 < jc["max_participants"] <= 250, (label, jc)
    assert jc["status_callback"].endswith("/conference-status"), (label, jc)
    return jc


def main():
    V.sdk_banner()
    import app as recipe

    guest = room_of(recipe.build().get_document(), "guest")
    host = room_of(recipe.build(host=True).get_document(), "host")
    yaml = room_of(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    # Same room for everyone: that is what puts them in one conference.
    assert guest["name"] == host["name"] == yaml["name"] == ROOM

    # The room's lifetime belongs to the host alone.
    assert host["start_on_enter"] is True and host["end_on_exit"] is True, host
    assert guest["start_on_enter"] is False and guest["end_on_exit"] is False, guest
    # a guest hanging up must not close the room, and must not open it
    assert yaml["end_on_exit"] is False, yaml
    assert yaml["start_on_enter"] is False, yaml

    # Members are controlled over documented Compatibility requests.
    rec = V.Recorder()
    V.record_everything(recipe.client, rec)

    recipe.mute(CONF, CALL)
    recipe.mute(CONF, CALL, muted=False)
    recipe.remove(CONF, CALL)
    recipe.who_is_in(CONF)
    assert len(rec.calls) == 4, rec.calls

    participant = f"/Accounts/proj-1234/Conferences/{CONF}/Participants/{CALL}"
    listing = f"/Accounts/proj-1234/Conferences/{CONF}/Participants"

    muted, unmuted, removed, listed = rec.calls
    for call, method, path in ((muted, "POST", participant),
                               (unmuted, "POST", participant),
                               (removed, "DELETE", participant),
                               (listed, "GET", listing)):
        assert call["path"].endswith(path.split("/Accounts/proj-1234")[1]), call
        assert call["method"] == method, call
        V.assert_documented("compat", method, call["path"], call["body"])

    assert muted["body"] == {"Muted": "true"}, muted
    assert unmuted["body"] == {"Muted": "false"}, unmuted

    # The webhook records the conference SID on join. Only one event can be
    # subscribed, and these documents ask for join, so nothing here pretends
    # to see departures.
    for doc in (recipe.build().get_document(),
                recipe.build(host=True).get_document()):
        assert V.first(doc, "join_conference")["status_callback_event"] == "join"
    client = recipe.app.test_client()
    client.post("/conference-status",
                data={"CallSid": CALL, "ConferenceSid": CONF})
    assert recipe.present[CALL] == CONF, recipe.present

    print(f"ok: three documents name {ROOM!r}; only the host starts and ends "
          f"it; mute, unmute, remove and list are documented compat requests")


if __name__ == "__main__":
    main()
