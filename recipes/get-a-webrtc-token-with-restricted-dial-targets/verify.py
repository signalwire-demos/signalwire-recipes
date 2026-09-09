"""Prove the claim without a network.

Claim: a guest token can only dial the addresses you list, and a visitor cannot
reach anything else.

Proof: with the HTTP layer replaced by a recorder, the route makes one
documented POST whose `allowed_addresses` is exactly the list for that page,
built server-side. An address the browser asks for is never honoured, an
unknown page mints nothing at all, and the response carries the token and no
project credentials.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-secret-do-not-leak",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
})

import verifylib as V  # noqa: E402

PATH = "/api/fabric/guests/tokens"


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"token": "gt-abc"}] * 6)
    V.record_everything(recipe.client, rec)
    client = recipe.app.test_client()

    # A page with one desk.
    r = client.post("/token", json={"page": "support"})
    assert r.status_code == 200, r.data
    assert r.get_json() == {"token": "gt-abc"}, r.get_json()

    assert len(rec.calls) == 1, rec.calls
    call = rec.calls[0]
    assert (call["method"], call["path"]) == ("POST", PATH), call
    V.assert_documented("rest", "POST", PATH, call["body"])
    assert call["body"]["allowed_addresses"] == ["/public/support"], call

    # The documented ceiling, and an expiry.
    assert len(call["body"]["allowed_addresses"]) <= recipe.MAX_ADDRESSES, call
    assert call["body"]["expire_at"] > 0, call

    # A page offering a choice gets exactly that choice.
    client.post("/token", json={"page": "contact"})
    assert rec.calls[-1]["body"]["allowed_addresses"] == [
        "/public/support", "/public/sales"], rec.calls[-1]

    # The browser selects a key and cannot add to the table. Asking for an
    # address outright changes nothing about what is minted; asking for
    # another page is allowed by design, which is why every desk in the table
    # has to be one any visitor may reach.
    before = len(rec.calls)
    r = client.post("/token", json={"page": "support",
                                    "allowed_addresses": ["/public/billing"],
                                    "address": "/private/finance"})
    assert r.status_code == 200, r.data
    minted = rec.calls[-1]["body"]["allowed_addresses"]
    assert minted == ["/public/support"], minted
    assert "/public/billing" not in str(rec.calls[-1]), rec.calls[-1]
    assert len(rec.calls) == before + 1, rec.calls

    # An unknown page mints nothing rather than minting something empty.
    before = len(rec.calls)
    for unknown in ({"page": "billing"}, {"page": ""}, {}):
        r = client.post("/token", json=unknown)
        assert r.status_code == 404, (unknown, r.data)
    assert len(rec.calls) == before, rec.calls

    # The project token stays on the server.
    body = client.post("/token", json={"page": "sales"}).get_data(as_text=True)
    assert os.environ["SIGNALWIRE_API_TOKEN"] not in body, body
    assert "proj-1234" not in body, body

    print(f"ok: POST {PATH} with allowed_addresses built server-side; a "
          f"browser-supplied address is ignored, an unknown page mints "
          f"nothing, and no credential reaches the response")


if __name__ == "__main__":
    main()
