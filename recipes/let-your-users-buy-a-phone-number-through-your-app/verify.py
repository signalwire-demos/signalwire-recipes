"""Prove the claim without a network.

Claim: onboarding uses your credentials, and every number request after it uses
the tenant's. The subproject and its token are created with the platform
client; the search, the purchase, the handler update, the list and the release
all travel on a client built from the tenant's project id and token. A record
without a token is refused rather than served by the platform client.

Proof: two recorders, one per client, and the platform client has every
namespace recorded, so a number request sent on it fails the run instead of
leaving the machine. The platform recorder sees the two onboarding requests and
nothing else. Every client the app builds afterwards carries the tenant's
basic-auth pair, never yours. Each request is checked against the vendored spec:
the token permission enum, the required `number` on a purchase, the documented
update fields and the call handler enum. The permission list, like every other
expected value, is stated here rather than read from app.py.

The TypeScript surface is held to the same values. Its recorder replaces
globalThis.fetch before any client exists, so every request carries the
basic-auth pair it would have been sent with, and the identity is read back off
the wire rather than inferred from which recorder saw it.
"""
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
PLATFORM_PROJECT = "proj-1234"
PLATFORM_TOKEN = "PT-platform"
SPACE = "example.signalwire.com"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": PLATFORM_PROJECT,
    "SIGNALWIRE_API_TOKEN": PLATFORM_TOKEN,
    "SIGNALWIRE_SPACE": SPACE,
})

import verifylib as V  # noqa: E402

TENANT = "Acme Dental"
TENANT_PROJECT = "9b1c7e42-5a3d-4f61-8c2e-0d7a6b5f4e30"
TENANT_TOKEN = "PT-tenant"
TOKEN_ID = "5c4b3a2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d"
NUMBER = "+14155550123"
NUMBER_ID = "3f2a1c88-77bd-4e15-9a02-6c5b4d3e2f10"
HOOK = "https://app.example.com/acme/"
NUMBERS = "/api/relay/rest/phone_numbers"
# stated here, never read from app.py: the recipe's list is compared to this
WANT_PERMISSIONS = ["numbers", "calling", "messaging"]
HANDLER = "relay_script"


def main():
    V.sdk_banner()
    import app as recipe

    store = pathlib.Path(tempfile.mkdtemp()) / "tenants.json"
    recipe.TENANTS_PATH = store

    platform = V.Recorder(responses=[
        {"id": TENANT_PROJECT, "name": TENANT, "subproject": True,
         "parent_project_id": PLATFORM_PROJECT},
        {"id": TOKEN_ID, "name": f"{TENANT} numbers",
         "permissions": WANT_PERMISSIONS, "token": TENANT_TOKEN},
    ])
    # every namespace, not just the two the recipe happens to use: a number
    # request sent on the platform client must be recorded here, not sent
    V.record_everything(recipe.platform, platform)

    tenant_rec = V.Recorder(responses=[
        {"data": [{"number": NUMBER, "region": "CA", "city": "SAN FRANCISCO"}]},
        {"id": NUMBER_ID, "number": NUMBER, "number_type": "longcode"},
        {"id": NUMBER_ID, "number": NUMBER, "call_handler": HANDLER,
         "name": TENANT},
        {"data": [{"id": NUMBER_ID, "number": NUMBER}]},
        {},
    ])
    built = []
    real_rest_client = recipe.RestClient

    def spy(project=None, token=None, host=None):
        client = real_rest_client(project=project, token=token, host=host)
        built.append({"project": project, "token": token, "host": host,
                      "auth": client._http._session.auth})
        V.record_everything(client, tenant_rec)
        return client

    recipe.RestClient = spy

    assert list(recipe.PERMISSIONS) == WANT_PERMISSIONS, recipe.PERMISSIONS
    record = recipe.onboard(TENANT)
    assert record == {"name": TENANT, "project_id": TENANT_PROJECT,
                      "token_id": TOKEN_ID, "permissions": WANT_PERMISSIONS,
                      "token": TENANT_TOKEN}, record
    # the id the token's own PATCH and DELETE need, since nothing lists tokens
    spec_paths = V.spec("rest")["paths"]
    assert set(spec_paths["/api/project/tokens/{token_id}"]) == {"patch", "delete"}
    assert "get" not in spec_paths["/api/project/tokens"]
    # the record survives the process, because the token is shown once
    assert json.loads(store.read_text(encoding="utf-8")) == {TENANT: record}
    assert built == [], "onboarding must use the platform client"

    # a record with no token is refused, and builds no client
    for broken in ({"name": TENANT, "project_id": TENANT_PROJECT, "token": ""},
                   {"name": TENANT, "project_id": "", "token": TENANT_TOKEN}):
        try:
            recipe.as_tenant(broken)
        except ValueError as exc:
            assert "refusing" in str(exc), exc
        else:
            raise AssertionError("acted for a tenant with no credentials")
    assert built == [], built

    stored = recipe.tenant(TENANT)
    assert recipe.offer(stored, "415") == [NUMBER]
    # the purchase response, not the handler update that follows it
    bought = recipe.buy(stored, NUMBER, HOOK)
    assert bought == {"id": NUMBER_ID, "number": NUMBER,
                      "number_type": "longcode"}, bought
    assert recipe.numbers(stored) == {"data": [{"id": NUMBER_ID, "number": NUMBER}]}
    recipe.release(stored, NUMBER_ID)

    # four clients for five requests: buy reuses one for the purchase and the
    # handler update. Every one of them authenticates as the tenant
    assert len(built) == 4, built
    for client in built:
        assert client["project"] == TENANT_PROJECT, client
        assert client["token"] == TENANT_TOKEN, client
        assert client["host"] == SPACE, client
        assert client["auth"] == (TENANT_PROJECT, TENANT_TOKEN), client

    # the platform client sent the two onboarding requests and nothing else
    assert [(c["method"], c["path"]) for c in platform.calls] == [
        ("POST", "/api/projects"), ("POST", "/api/project/tokens")], platform.calls
    project_body = platform.calls[0]["body"]
    assert project_body == {"name": TENANT, "force_https_requests": True}
    V.assert_documented("rest", "POST", "/api/projects", project_body)
    token_body = platform.calls[1]["body"]
    assert token_body == {"name": f"{TENANT} numbers",
                          "permissions": WANT_PERMISSIONS,
                          "subproject_id": TENANT_PROJECT}, token_body
    V.assert_documented("rest", "POST", "/api/project/tokens", token_body)

    spec = V.spec("rest")
    allowed = spec["components"]["schemas"]["Project.TokenPermission"]["enum"]
    assert set(WANT_PERMISSIONS) <= set(allowed), WANT_PERMISSIONS
    assert "numbers" in WANT_PERMISSIONS, WANT_PERMISSIONS
    assert "management" not in WANT_PERMISSIONS, WANT_PERMISSIONS

    # and the tenant client sent every number request
    sent = [(c["method"], c["path"]) for c in tenant_rec.calls]
    assert sent == [("GET", NUMBERS + "/search"), ("POST", NUMBERS),
                    ("PUT", f"{NUMBERS}/{NUMBER_ID}"), ("GET", NUMBERS),
                    ("DELETE", f"{NUMBERS}/{NUMBER_ID}")], sent

    search = tenant_rec.calls[0]
    assert search["params"] == {"areacode": "415", "number_type": "local",
                                "max_results": 5}, search
    V.assert_documented("rest", "GET", NUMBERS + "/search", None, search["params"])
    # the number the tenant is offered is the field the spec marks required
    available = spec["components"]["schemas"]["AvailablePhoneNumber"]
    assert available["required"] == ["number"], available

    purchase = tenant_rec.calls[1]["body"]
    assert purchase == {"number": NUMBER}, purchase
    V.assert_documented("rest", "POST", NUMBERS, purchase)

    update = tenant_rec.calls[2]["body"]
    assert update == {"name": TENANT, "call_handler": HANDLER,
                      "call_relay_script_url": HOOK}, update
    V.assert_documented("rest", "PUT", f"{NUMBERS}/{NUMBER_ID}", update)
    # assert_documented checks the key, not the value, so read the enum
    handlers = spec["components"]["schemas"]["PhoneNumberCallHandlerRequest"]["enum"]
    assert update["call_handler"] in handlers, (update["call_handler"], handlers)
    V.assert_documented("rest", "GET", NUMBERS, None)
    V.assert_documented("rest", "DELETE", f"{NUMBERS}/{NUMBER_ID}", None)

    # the TypeScript surface, held to the same expectations
    node = V.node_surface(HERE, TENANT, TENANT_PROJECT, TOKEN_ID, TENANT_TOKEN,
                          NUMBER, HOOK)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["permissions"] == WANT_PERMISSIONS, node["permissions"]
        assert node["record"] == {"name": TENANT, "project_id": TENANT_PROJECT,
                                  "token_id": TOKEN_ID,
                                  "permissions": WANT_PERMISSIONS,
                                  "token": TENANT_TOKEN}, node["record"]
        assert len(node["refused"]) == 2, node["refused"]
        assert all("refusing" in r for r in node["refused"]), node["refused"]
        assert node["offered"] == [NUMBER], node["offered"]

        sent = [(c["method"], c["path"]) for c in node["captured"]]
        assert sent == [("POST", "/api/projects"), ("POST", "/api/project/tokens"),
                        ("GET", NUMBERS + "/search"), ("POST", NUMBERS),
                        ("PUT", f"{NUMBERS}/number-1"), ("GET", NUMBERS),
                        ("DELETE", f"{NUMBERS}/number-1")], sent
        # who each request went out as, read off the Authorization header
        onboarding, numbers = node["captured"][:2], node["captured"][2:]
        assert node["onboardingRequests"] == 2, node["onboardingRequests"]
        assert [c["project"] for c in onboarding] == [PLATFORM_PROJECT] * 2, onboarding
        assert [c["project"] for c in numbers] == [TENANT_PROJECT] * 5, numbers
        assert PLATFORM_PROJECT not in [c["project"] for c in numbers], numbers

        assert onboarding[0]["body"] == project_body, onboarding[0]
        assert onboarding[1]["body"] == token_body, onboarding[1]
        # the spec's query param is lower case, and the SDK passes keys through
        assert numbers[0]["query"] == ("?areacode=415&number_type=local"
                                       "&max_results=5"), numbers[0]
        assert numbers[1]["body"] == purchase, numbers[1]
        assert numbers[2]["body"] == update, numbers[2]
        ts_note = ("typescript sends the same requests, with onboarding as the "
                   "platform and every number request as the tenant")

    print(f"ok: onboarding sent POST /api/projects and POST /api/project/tokens on "
          f"the platform client; the search, purchase, handler update, list and "
          f"release all travelled on clients authenticating as {TENANT_PROJECT[:8]}"
          f"...; the platform client sent no number request, and a record without a "
          f"token is refused; {ts_note}")


if __name__ == "__main__":
    main()
