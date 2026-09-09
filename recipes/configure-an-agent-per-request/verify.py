"""Prove the claim without a network.

Claim: one deployed agent serves many tenants. The prompt, the voice and the
global_data in the document are chosen per request from the query string or a
header, and the deployed agent itself is not changed by any request.

Proof: drive the agent's own HTTP app with FastAPI's test client and GET the
SWML the way the platform does. `?tenant=harbor` yields Harbor's voice, a
Tenant prompt section naming Harbor, and `global_data.tenant` of harbor;
`?tenant=ridgeline` yields Ridgeline's; an `X-Tenant` header passes the same
assertion; an unknown tenant passes the default tenant's. After all of that,
the deployed agent renders the same document it rendered before the first
request, because each request configured an ephemeral copy. Expected values
live here, not in app.py.
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

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")
os.environ["DEFAULT_TENANT"] = "ridgeline"

# Expected values live here, not imported from app.py.
EXPECT = {
    "ridgeline": ("Ridgeline Cycles", "rime.spore"),
    "harbor": ("Harbor Bike Repair", "rime.marisol"),
}


def basic_auth():
    raw = f"{os.environ['SWML_BASIC_AUTH_USER']}:{os.environ['SWML_BASIC_AUTH_PASSWORD']}"
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}


def ai_of(doc):
    V.validate_swml(doc)
    return next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]


def tenant_section(ai):
    return next((s for s in ai["prompt"]["pom"] if s["title"] == "Tenant"), None)


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    from app import FrontDeskAgent

    agent = FrontDeskAgent()
    V.assert_basic_auth_from_env(agent)
    client = TestClient(agent.get_app())
    before = agent._render_swml()  # the deployed agent, before any request

    root = agent.route + "/"

    def fetch(query="", headers=None):
        r = client.get(root + query, headers={**basic_auth(), **(headers or {})})
        assert r.status_code == 200, (query, r.status_code, r.text)
        return ai_of(r.json())

    # the route is behind basic auth like every other AgentBase route
    assert client.get(root + "?tenant=harbor").status_code == 401

    # the trap: in 3.0.1 the root is registered only with its trailing slash.
    # Without it the request falls to a catch-all that answers 200 "null", so
    # a number pointed at .../front-desk gets no document at all.
    r = client.get(agent.route + "?tenant=harbor", headers=basic_auth())
    assert (r.status_code, r.text) == (200, "null"), (r.status_code, r.text)

    def expect_tenant(ai, key):
        """One assertion for every way a tenant can be selected."""
        shop, voice = EXPECT[key]
        assert ai["languages"] == [{"name": "English", "code": "en-US",
                                    "voice": voice}], (key, ai["languages"])
        sec = tenant_section(ai)
        assert sec and shop in sec["body"], (key, sec)
        assert ai["global_data"] == {"tenant": key, "shop": shop}, (key, ai["global_data"])
        # the shared Role section is still there, first
        assert ai["prompt"]["pom"][0]["title"] == "Role", ai["prompt"]["pom"][0]
        # and exactly one Tenant section, not one per request so far
        assert sum(s["title"] == "Tenant" for s in ai["prompt"]["pom"]) == 1

    requests = 0
    # one URL per tenant, one deployed agent
    for key in EXPECT:
        expect_tenant(fetch(f"?tenant={key}"), key)
        requests += 1

    # a header does the same job as the query string
    expect_tenant(fetch(headers={"X-Tenant": "harbor"}), "harbor")
    requests += 1

    # an unknown tenant gets the default tenant's whole configuration
    expect_tenant(fetch("?tenant=nobody"), "ridgeline")
    requests += 1

    # the deployed agent was never touched: it renders the same document as
    # before any request. Each request configured an ephemeral copy.
    after = agent._render_swml()
    assert after == before, "the deployed agent changed"
    base = ai_of(json.loads(after))
    assert tenant_section(base) is None, [s["title"] for s in base["prompt"]["pom"]]
    assert "languages" not in base, base.get("languages")

    print(f"ok: ?tenant= and X-Tenant select {sorted(EXPECT)} with their own voice, "
          f"Tenant section and global_data; unknown falls back to ridgeline's whole "
          f"configuration; the deployed agent renders byte-for-byte the same after "
          f"{requests} requests")


if __name__ == "__main__":
    main()
