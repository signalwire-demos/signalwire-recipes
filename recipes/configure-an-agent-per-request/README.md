# Configure a voice AI agent per request for many tenants

> One deployed agent serves many tenants. A callback runs on every SWML request and configures an ephemeral copy from the query string or a header, so the deployed agent never changes.

**Scenario:** two bicycle shops sharing one front-desk deployment

## What this demonstrates

`set_dynamic_config_callback` registers a function the SDK calls on every SWML
request with the query parameters, the POST body, the headers and an agent to
configure. That agent is an ephemeral copy. Your callback adds a prompt section,
a voice and `global_data` for the tenant the request names. The SDK renders the
document from the copy and leaves the deployed agent as it was.

The mechanism is the SDK's: `set_dynamic_config_callback` in `web_mixin.py`,
and `_create_ephemeral_copy` in `agent_base.py`, which copies the prompt,
languages, params and `global_data` before the callback runs.

## How it works

```python
def configure(query_params, body_params, headers, agent):
    key = (query_params.get("tenant") or headers.get("x-tenant") or DEFAULT_TENANT).lower()
    tenant = TENANTS.get(key) or TENANTS[DEFAULT_TENANT]
    agent.prompt_add_section("Tenant", f"You answer for {tenant['name']}. ...")
    agent.add_language("English", "en-US", tenant["voice"])
    agent.set_global_data({"tenant": key, "shop": tenant["name"]})

class FrontDeskAgent(AgentBase):
    def __init__(self):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", "You are a bicycle shop's front desk. ...")
        self.set_dynamic_config_callback(configure)
```

The document rendered for `?tenant=harbor` contains this `ai` object:

```json
{"prompt": {"pom": [{"title": "Role", "body": "..."}, {"title": "Tenant", "body": "You answer for Harbor Bike Repair. ..."}]},
 "languages": [{"name": "English", "code": "en-US", "voice": "rime.marisol"}],
 "global_data": {"tenant": "harbor", "shop": "Harbor Bike Repair"}}
```

What every tenant shares stays on the deployed agent. What differs is a
dictionary here and a database row in production, keyed by the tenant id.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point one number at
`https://<user>:<password>@<your-host>/front-desk/?tenant=ridgeline` and another
at the same URL with `?tenant=harbor`. The trailing slash matters; see
Limitations.

## Verify it

No network, no account. The verifier drives the agent's own HTTP app with
FastAPI's test client and fetches the SWML the way the platform does.

```bash
python verify.py          # from the recipe folder, not python/
```

It asserts the following.

- a GET without basic auth is refused
- `?tenant=harbor` and `?tenant=ridgeline` each render their own voice, one `Tenant` section naming their shop, and `global_data` with their key, with the shared `Role` section first
- an `X-Tenant: harbor` header passes the same voice, section and `global_data` assertion as the query string
- `?tenant=nobody` passes the default tenant's assertion in full
- after all of those requests, the deployed agent renders byte-for-byte the document it rendered before the first one
- a GET on the route without its trailing slash returns `200` with a body of `null`

## Limitations

SDK 3.0.1 registers the agent's root only as `/front-desk/`. A request to
`/front-desk` falls through to a catch-all that answers `200 null`. A number
pointed at the URL without the slash gets no document. The verifier asserts this
so the trap is on record.

This recipe changes the prompt, the voice and `global_data` per request. You
register tools on the deployed agent, and every tenant shares them.

## What to change first

Delete the `agent.add_language(...)` line from the callback and add
`self.add_language("English", "en-US", TENANTS[DEFAULT_TENANT]["voice"])` to
`__init__`, then run the verifier. Both tenants now render the same voice and
Harbor's assertion fails. That is the point: what sits on the deployed agent is
what every tenant gets.
