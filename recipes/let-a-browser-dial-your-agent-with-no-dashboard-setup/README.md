# Let a browser dial your agent with no dashboard setup

> A SWML webhook resource whose `primary_request_url` is your agent's URL is a thing a browser can dial: you list its Fabric addresses over REST and mint a guest token whose `allowed_addresses` names one, with no Dashboard step.

**Scenario:** a support page whose "talk to us" button should reach the agent you deployed a minute ago, with no Dashboard visit first

## What this demonstrates

Three REST calls the vendored spec documents. `POST /api/fabric/resources/swml_webhooks`
creates a resource. Its one required field is `primary_request_url`, "Primary
URL SignalWire fetches the SWML document from when the webhook fires".
`used_for` says whether it handles calls or messages.
`GET /api/fabric/resources/{id}/addresses` lists the resource's Fabric
addresses, each with an `id`, a `name` and its `channels`. That an address is
there to list is the platform's side; the recipe asks until one is.
`POST /api/fabric/guests/tokens` requires `allowed_addresses`, "List of up to
10 UUIDs representing the allowed Fabric addresses", takes an `expire_at`, and
answers `201` with `token` and `refresh_token`. You reach them as
`client.fabric.swml_webhooks.create`, `list_addresses` and
`client.fabric.tokens.create_guest_token`.

## How it works

```python
def register(name="front-desk", wait=time.sleep):
    resource = client.fabric.swml_webhooks.create(
        name=name, used_for="calling", primary_request_url=AGENT_URL,
        primary_request_method="POST")
    for attempt in range(ADDRESS_TRIES):                 # the list can lag the create
        listed = client.fabric.swml_webhooks.list_addresses(resource["id"])
        addresses = listed.get("data", [])
        if addresses:
            return resource["id"], addresses[0]
        if attempt < ADDRESS_TRIES - 1:
            wait(1)
    raise RuntimeError(f"resource {resource['id']} listed no address after {ADDRESS_TRIES} tries")

def guest_token(address_id, now=None):
    if now is None:
        now = time.time()
    return client.fabric.tokens.create_guest_token(
        allowed_addresses=[address_id], expire_at=int(now) + TOKEN_TTL_SECONDS)
```

What the platform receives:

```http
POST /api/fabric/resources/swml_webhooks
{"name": "front-desk", "used_for": "calling",
 "primary_request_url": "https://<user>:<password>@<your-host>/front-desk/",
 "primary_request_method": "POST"}

GET /api/fabric/resources/<resource_id>/addresses

POST /api/fabric/guests/tokens
{"allowed_addresses": ["<address_id>"], "expire_at": 1788351300}
```

The agent URL carries the agent's basic-auth pair, the `SWML_BASIC_AUTH_*`
values from the agent's own `.env`, because the platform fetches the document
from it. The spec does not say when the address appears, so `register` asks up
to five times, a second apart, and fails with a message rather than an
`IndexError`. A guest token names one address and expires. Your page asks your
server for a fresh one and hands it to the Browser SDK, which is the client
side and outside this recipe.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials and AGENT_URL
python app.py register           # once: prints the resource id and the address
python app.py token YOUR_ADDRESS_ID   # per visitor: a token good for TOKEN_TTL_SECONDS
```

Replace `YOUR_ADDRESS_ID` with the address id `register` printed.

There is no server to expose here; the script speaks to the REST API and
exits. `AGENT_URL` is the public URL of an agent you already run, for example
`route-a-call-to-an-ai-agent` behind a tunnel, with its basic-auth pair in the
URL. The browser side is `call-from-a-browser`: give its client the token and
the address name.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder that answers with a resource, one
address and one token, and you inject the clock. You call both helpers and
assert the following.

- `register` makes one `POST` to the documented SWML webhooks path with exactly `name`, `used_for`, `primary_request_url` and `primary_request_method`
- it then asks for the resource's addresses with no body or query, and when the first answer is empty it waits a second and asks again
- a resource that lists no address after five tries fails with a message that names the resource and the count, after four waits, and the token client saw no request
- `guest_token` makes one `POST` to the documented guest tokens path with exactly the one address id and `expire_at` 900 seconds after the injected clock
- a clock of zero is a clock, not a missing argument: `expire_at` is 900
- the spec requires exactly `primary_request_url` on the resource and exactly `allowed_addresses` on the token, and says the list holds up to 10 addresses
- `calling` and `POST` are in the spec's enums for `used_for` and the request method
- the guest token answers `201` with `token` and `refresh_token`; the address list carries `id`, `name` and `channels`, and the fixture uses only documented fields

## Limitations

You prove the requests and the documented shapes. Whether the address rings
your agent, and what the browser hears, are the platform's side of a live call.

A guest token is a credential. Mint it on your server per visitor and hand it
over HTTPS; the default fifteen-minute `expire_at` here is the recipe's choice.

## What to change first

Change `guest_token` to take a list of address ids as its first argument, pass
two, and run the verifier. The exact-body assertion fails. The spec says why
you might want that anyway: a token may allow up to ten addresses, so one page
can reach several desks.
