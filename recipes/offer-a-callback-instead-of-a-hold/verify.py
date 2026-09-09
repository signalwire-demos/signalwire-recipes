"""Prove the claim without a network.

Claim: a waiting caller is released with a promise, and the return call opens
with the context they already gave.

Proof: the queue document caps the wait and puts the release path after
`enter_queue`, which is the only shape available because a leg already waiting
cannot be redirected into new SWML. The outbound call carries the context in
the document handed to `dial`, so the returning caller is told why they are
being rung rather than asked again.
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
    "SIGNALWIRE_PHONE_NUMBER": "+15550001111",
    "PUBLIC_URL": "https://recipes.example.test",
    "QUEUE_NAME": "support",
    "MAX_WAIT_SECONDS": "180",
})

import verifylib as V  # noqa: E402

CALLER = "+15552223333"


def main():
    V.sdk_banner()
    import app as recipe

    # --- the wait, and the way out of it -------------------------------
    doc = recipe.build().get_document()
    V.validate_swml(doc)
    names = V.verb_names(doc)
    assert names == ["answer", "enter_queue", "play", "hangup"], names

    eq = V.first(doc, "enter_queue")
    assert eq["queue_name"] == "support", eq
    # a string, not a boolean: the field holds a URL or inline SWML
    assert eq["transfer_after_bridge"] == "false", eq
    # the cap is what makes the release reachable at all
    assert eq["wait_time"] == recipe.MAX_WAIT > 0, eq
    assert eq["wait_url"] and eq["status_url"], eq

    # The release path is after enter_queue, because a leg already waiting
    # cannot be redirected into new SWML.
    assert names.index("play") > names.index("enter_queue"), names
    promise = V.first(doc, "play")["url"]
    assert "call you back" in promise, promise
    # the promise has to be a promise, not a request to hold
    assert "hold" not in promise.lower(), promise

    # --- hold audio: wait_url has to point at something ------------------
    client = recipe.app.test_client()
    hold = client.get("/hold-music").get_json()
    V.validate_swml(hold)
    assert V.verb_names(hold) == ["play"], hold

    # --- remembering is not owing ----------------------------------------
    assert recipe.remember(CALLER, "a refund on order 48815") is True
    assert recipe.context[CALLER]["reason"] == "a refund on order 48815"
    # A caller who reached an agent is remembered and owed nothing, so
    # call_back does not ring them.
    assert CALLER not in recipe.owed, recipe.owed

    # --- owing happens when the wait ran out ------------------------------
    assert recipe.owe_callback(CALLER) is True
    assert recipe.owed[CALLER]["reason"] == "a refund on order 48815", recipe.owed
    # a promise you cannot ring is not a promise
    assert recipe.owe_callback("") is False
    assert recipe.owe_callback(None) is False
    assert len(recipe.owed) == 1, recipe.owed

    # --- the return call carries what they said --------------------------
    rec = V.Recorder()
    recipe.client.calling._http = rec
    recipe.call_back(CALLER)

    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    assert (call["method"], call["path"]) == ("POST", "/api/calling/calls"), call
    params = call["body"]["params"]
    assert call["body"]["command"] == "dial", call
    assert params["to"] == CALLER and params["from"] == recipe.FROM, params

    # The context travels in the document, not in a lookup the caller waits on.
    returned = params["swml"]
    V.validate_swml(returned)
    said = V.first(returned, "play")["url"]
    assert "a refund on order 48815" in said, said
    assert "callback you asked for" in said, said
    # and it puts them back in the queue they left
    assert V.first(returned, "connect")["to"] == "queue:support", returned

    # The promise is discharged, so a restart cannot ring them twice.
    assert CALLER not in recipe.owed, recipe.owed

    # Discharged: a second call_back rings nobody.
    before = len(rec.calls)
    assert recipe.call_back(CALLER) is None
    assert len(rec.calls) == before, rec.calls
    # and a caller who was never owed anything is never dialled
    assert recipe.call_back("+15558887777") is None
    assert len(rec.calls) == before, rec.calls

    # A caller with no recorded context still gets a sensible call.
    recipe.remember(CALLER, "")
    recipe.owe_callback(CALLER)
    recipe.call_back(CALLER)
    bare = V.first(rec.calls[-1]["body"]["params"]["swml"], "play")["url"]
    assert "your call earlier" in bare, bare

    # A dial that fails keeps the promise. Discharging first would drop the
    # caller silently, which is the one outcome this recipe exists to avoid.
    class Fails:
        def post(self, *a, **k):
            raise RuntimeError("network")

    recipe.remember(CALLER, "a refund on order 48815")
    recipe.owe_callback(CALLER)
    recipe.client.calling._http = Fails()
    try:
        recipe.call_back(CALLER)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the dial to raise")
    assert CALLER in recipe.owed, recipe.owed
    assert recipe.owed[CALLER]["reason"] == "a refund on order 48815", recipe.owed

    print(f"ok: enter_queue(wait_time={eq['wait_time']}) with the release path "
          f"after it; the callback dials {CALLER} carrying the reason they "
          f"gave, and the promise is discharged")


if __name__ == "__main__":
    main()
