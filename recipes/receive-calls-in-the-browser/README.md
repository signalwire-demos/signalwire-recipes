# Receive calls in the browser

> A subscriber is a Fabric resource with an address of its own, and a subscriber token is what a browser registers with. A SWML `connect` to that address is the document that sends a call to the registered browser.

**Scenario:** a workshop mechanic who takes the shop's calls at a laptop, with no desk phone

## What this demonstrates

Three documented pieces. `POST /api/fabric/resources/subscribers` creates the
person as a resource; the vendored REST spec requires one field, `email`.
`GET /api/fabric/resources/{id}/addresses` lists the addresses the subscriber
got, each with a `name` such as `/private/dana` and its `channels`.
`POST /api/fabric/subscribers/tokens` requires `reference`, "A string that
uniquely identifies the subscriber. Often it's an email". It answers with
`subscriber_id`, `token` and `refresh_token`. The bundled schema lists a "Call
Fabric Resource address" among the forms `connect.to` takes. A document that
connects to the subscriber's address is therefore the document that sends a
call to them. Whether it rings is the platform's side of a live call.
You reach the REST calls as `client.fabric.subscribers.create`, `list_addresses`
and `client.fabric.tokens.create_subscriber_token`.

## How it works

```python
def create_subscriber(email=EMAIL, display_name=DISPLAY_NAME):
    resource = client.fabric.subscribers.create(email=email, display_name=display_name)
    addresses = client.fabric.subscribers.list_addresses(resource["id"]).get("data", [])
    if not addresses:
        raise RuntimeError(f"subscriber {resource['id']} listed no address")
    return resource["id"], addresses[0]["name"]

def browser_token(email=EMAIL):
    return client.fabric.tokens.create_subscriber_token(reference=email)

def ring(address, service=None):
    service = service or SWMLService(name="ring", route="/ring")
    service.add_verb("answer", {})
    service.add_verb("play", {"url": "say:Connecting you to the workshop."})
    service.add_verb("connect", {"to": address, "timeout": 30})
    service.add_verb("hangup", {})
    return service
```

What the platform receives:

```http
POST /api/fabric/resources/subscribers
{"email": "dana@ridgeline.example", "display_name": "Dana at the workshop"}

GET /api/fabric/resources/<resource_id>/addresses

POST /api/fabric/subscribers/tokens
{"reference": "dana@ridgeline.example"}
```

And the document a number runs, with the address from the listing:

```json
{"version": "1.0.0", "sections": {"main": [
  {"answer": {}}, {"play": {"url": "say:Connecting you to the workshop."}},
  {"connect": {"to": "/private/dana", "timeout": 30}}, {"hangup": {}}]}}
```

The browser side is `typescript/index.ts`, on the Browser SDK v3. It builds a
client from the subscriber token and registers with `client.online`. Each call
arrives at the handler as an `invite`. `accept({rootElement})` renders the call
into an element and `reject()` declines it. The token is per person and
expires, so your server mints one when the mechanic signs in. The page here
takes it pasted, because the recipe runs no server.

```ts
const client = await SignalWire({ token });
await client.online({ incomingCallHandlers: { all: (n) => { pending = n.invite; } } });
await pending.accept({ rootElement: document.getElementById("call")! });
```

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, the subscriber's email and name
python app.py subscriber         # once: prints the resource id and the address
python app.py token              # per sign-in: the token the browser registers with
python app.py document /private/dana    # the SWML, to serve from a number's webhook
cd ../typescript && npm ci && npm start # the page: paste the token, go online, answer
```

There is no server to expose here; the script speaks to the REST API and
exits. Serve the document from any SWML webhook and point the shop's number at
it. Have the browser register with the token, then call the number.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder that answers with a resource, one
address and one token. You call the helpers and assert the following.

- `create_subscriber` makes one `POST` to the documented subscribers path with exactly `email` and `display_name`
- it then makes one `GET` of the resource's addresses with no body or query, and returns the address name
- a subscriber that lists no address fails with a message that names it
- `browser_token` makes one `POST` to the documented subscriber tokens path with exactly `reference`
- the spec requires exactly `email` on the subscriber and exactly `reference` on the token, and describes `reference` as what identifies the subscriber
- the token answers with `subscriber_id`, `token` and `refresh_token`; the address list carries `id`, `name` and `channels`, and the fixture uses only documented fields
- the document validates, its verbs are `answer`, `play`, `connect`, `hangup`, and `connect` is exactly the address with a 30-second timeout
- the bundled schema lists a Call Fabric Resource address among the forms `connect.to` takes
- the browser client builds a `SignalWire` client from a token, calls `client.online` with an `incomingCallHandlers` entry, and answers with `invite.accept` into a root element
- the client type-checks against the installed `@signalwire/js` when `typescript/node_modules` exists

## Limitations

You prove the requests, the shapes, the document and that the client compiles
against the SDK's types. Whether the browser rings, and what happens when
nobody is registered, are the platform's side of a live call.

A subscriber token is a credential for that person. Mint it on your server
after your own sign-in and hand it over HTTPS.

## What to change first

Change `ring` to connect to `EMAIL` instead of the address and run the
verifier. `add_verb` raises `SchemaValidationError` while the document is being
built, before any assertion runs. The schema's forms for `connect.to` are a
number, a SIP URI, a Fabric address or a queue, and an email is none of them.
