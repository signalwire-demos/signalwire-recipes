"""Prove the claim without a network.

Claim: one AgentServer routes SIP usernames on one domain to different agents.
A routing callback reads the username from the request body and the SDK
answers 307 with that agent's route. A re-POST to that route serves that
agent's SWML.

Proof: drive the server's own FastAPI app with the test client. A POST to
either agent's `/sip` path with `call.to` of `sip:workshop@...` answers 307
with `Location: /support/`. Re-POSTing the body there verbatim serves the
support desk's SWML. `sip:sales@...` does the same for `/sales/`. The slash is
load-bearing: an AgentBase root answers only at `/route/`. A `tel:` destination
and an unknown username answer 200 with the SWML of whichever agent received
the request, because the callback returned None. A request with no basic auth
is refused. The SDK's `extract_sip_username` is asserted on `sip:`, `tel:`,
bare and missing values. Expected values live here, not in app.py.
"""
import base64
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# fixed, verifier-only credentials
os.environ["SWML_BASIC_AUTH_USER"] = "signalwire"
os.environ["SWML_BASIC_AUTH_PASSWORD"] = "verify-only-password"

ROUTES = {"sales": "/sales/", "orders": "/sales/", "support": "/support/", "workshop": "/support/"}


def auth():
    return {"Authorization": "Basic " + base64.b64encode(
        b"signalwire:verify-only-password").decode()}


def body(to):
    return {"call": {"call_id": "c1", "to": to, "from": "sip:alice@phones.example.com"}}


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    from signalwire import SWMLService
    import app as recipe

    server = recipe.build_server(port=3000)
    for agent in server.agents.values():
        V.assert_basic_auth_from_env(agent)
    client = TestClient(server.app)

    # the SDK helper the callback relies on
    assert SWMLService.extract_sip_username(body("sip:Workshop@pbx.example.com")) == "Workshop"
    assert SWMLService.extract_sip_username(body("tel:+15550100001")) == "+15550100001"
    assert SWMLService.extract_sip_username(body("workshop")) == "workshop"
    assert SWMLService.extract_sip_username({}) is None

    DESK = {"/sales/": "sales desk", "/support/": "support desk"}

    def served_desk(response, to):
        assert response.status_code == 200, (to, response.status_code, response.text[:100])
        doc = response.json()
        V.validate_swml(doc)
        ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
        return json.dumps(ai["prompt"])

    # every username reaches its agent, from either agent's /sip path: a 307,
    # then the same body re-POSTed to Location serves that agent's document
    assert recipe.USERNAMES == ROUTES, (recipe.USERNAMES, ROUTES)
    for username, route in ROUTES.items():
        for entry in ("/sales", "/support"):
            # one of them arrives with the case a phone might send
            as_sent = username.capitalize() if username == "workshop" else username
            payload = body(f"sip:{as_sent}@pbx.example.com")
            r = client.post(f"{entry}/sip", json=payload, headers=auth(), follow_redirects=False)
            assert (r.status_code, r.headers.get("location")) == (307, route), \
                (username, entry, r.status_code, r.headers.get("location"))
            # Location verbatim: an AgentBase root answers only with the trailing
            # slash, so the route the callback returns must carry one
            hop = client.post(r.headers["location"], json=payload, headers=auth(),
                              follow_redirects=False)
            assert DESK[route] in served_desk(hop, username), (username, route)

    # no match: the callback returns None and whichever agent received the
    # request answers with its own document
    for entry, desk in DESK.items():
        for to in ("sip:nobody@pbx.example.com", "tel:+15550100001"):
            r = client.post(f"{entry.rstrip('/')}/sip", json=body(to), headers=auth(),
                            follow_redirects=False)
            assert desk in served_desk(r, to), (entry, to)

    # basic auth still gates the path
    r = client.post("/sales/sip", json=body("sip:workshop@pbx.example.com"),
                    follow_redirects=False)
    assert r.status_code == 401, r.status_code

    print(f"ok: {sorted(ROUTES)} redirect 307 to their agents from either /sip path and "
          f"the hop serves that agent's SWML; an unknown username and a tel: destination "
          f"get the receiving agent's own SWML; no auth is 401")


if __name__ == "__main__":
    main()
