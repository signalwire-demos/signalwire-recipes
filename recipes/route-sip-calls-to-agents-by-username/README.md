# Route SIP calls to AI agents by username

> One AgentServer routes SIP usernames on one domain to different agents. A routing callback reads the username from the request body and the SDK answers 307 with that agent's route. A re-POST to that route serves that agent's SWML.

**Scenario:** a PBX trunk that sends `sales@` and `workshop@` to one webhook and expects two different agents

## What this demonstrates

`register_routing_callback(fn, path)` on an agent mounts `path` under the
agent's route. When the platform POSTs there, the SDK calls `fn(request, body)`.
A returned route becomes a 307 redirect; `None` means "carry on and serve this
agent". `SWMLService.extract_sip_username(body)` reads the username out of
`call.to`. It takes the part before `@` of a `sip:` URI, the value after
`tel:`, or the bare value. A dictionary from username to route is the whole
router.

In 3.0.1 you must register the callback before `server.register(agent)`,
because that call copies the agent's routes into the app once. The server's own
`setup_sip_routing()` registers its callback after that copy and mounts no
`/sip` endpoint, which the verifier's design works around and Limitations
records.

## How it works

```python
USERNAMES = {"sales": "/sales/", "orders": "/sales/", "support": "/support/",
             "workshop": "/support/"}

def route_by_username(request, body):
    username = SWMLService.extract_sip_username(body)
    return USERNAMES.get((username or "").lower())

class DeskAgent(AgentBase):
    def __init__(self, name, route, role):
        super().__init__(name=name, route=route)
        self.prompt_add_section("Role", role)
        self.register_routing_callback(route_by_username, path="/sip")
```

What the platform sends and gets back for a call to the workshop:

```
POST /sales/sip
{"call": {"call_id": "...", "to": "sip:workshop@pbx.example.com", "from": "..."}}

HTTP/1.1 307 Temporary Redirect
Location: /support/
```

RFC 9110 defines 307 so that a client following it must not change the
request method. The section is https://www.rfc-editor.org/rfc/rfc9110#section-15.4.8.
The verifier does that step by hand: it re-POSTs the same body to `Location`
verbatim, and the support agent serves its SWML. The routes in `USERNAMES` end
in a slash on purpose. An AgentBase serves its root only at `/route/`, so a
`Location` of `/support` lands on a 404. A username the map does not know
returns `None` from the callback, and the agent that received the request
serves its own document.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. You also need a SIP domain
application. Create one in the Dashboard under SIP, or with
`POST /api/relay/rest/domain_applications` from the vendored REST spec. Register
your PBX or softphone against the domain it gives you. Point its call handler
at a SWML script at `https://<user>:<password>@<your-host>/sales/sip/`. Either
agent's `/sip` path routes for both. Dial `sip:workshop@<your-domain>`
and `sip:sales@<your-domain>`.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier builds the server, drives its FastAPI app with the test client, and
asserts the following.

- `extract_sip_username` returns the username of a `sip:` URI, the value after `tel:`, a bare value as itself, and `None` for a body with no call
- the app's `USERNAMES` equals the verifier's own map
- each of the four usernames, POSTed to either agent's `/sip` path, answers 307 with the mapped agent's route, slash included, in `Location`; one of them arrives as `Workshop`
- re-POSTing the same body to that `Location`, unchanged, answers 200 with the destination agent's SWML, which validates and names that desk
- an unknown username and a `tel:` destination, POSTed to each agent's `/sip` path, answer 200 with that receiving agent's own SWML
- the server refuses a POST without basic auth

## Limitations

`AgentServer.setup_sip_routing()` exists in 3.0.1 but mounts nothing: it
registers its callback after `server.register()` has already copied each
agent's routes. Register the callback on the agent first, as this recipe does.

Routing is by username only. The router ignores the domain part of the URI, so
two domains sharing a username share an agent.

## What to change first

Add `"billing": "/sales/"` to `USERNAMES` and run the verifier. It fails at
once, because it asserts its own `ROUTES` equals the app's map. Add the same
entry to `ROUTES` and it passes again. The two maps grow together, and the
dictionary is the router. To see the 3.0.1 ordering rule instead, register the callback after
`server.register()`. Every `/sip` POST becomes a 404.
