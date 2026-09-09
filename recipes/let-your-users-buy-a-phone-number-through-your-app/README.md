# Let your users buy a phone number through your app

> Onboarding uses your credentials. Every number request after it authenticates as the tenant's own project, so your platform token is never used on their behalf.

**Scenario:** your customers pick a local number during signup and give it back when they cancel

## What this demonstrates

Your app onboards a customer with two requests of yours, and then acts as them.
`POST /api/projects` creates their subproject, `POST /api/project/tokens`
issues a token bound to it, and every number request after that travels on a
second `RestClient` built from that project id and token.

The permissions are exactly the list you pass. This tenant gets `numbers`,
`calling` and `messaging`, and `management` is deliberately absent. The spec's
`Project.TokenPermission` enum is the whole vocabulary. Each phone number
operation here documents the `Numbers` scope, and both onboarding operations
document `Management`.

A stored record with no token raises. A missing credential is never quietly
replaced by yours, which matters because `RestClient()` falls back to the
environment when an argument is empty.

## How it works

```python
platform = RestClient()          # your credentials, used for onboarding only

def as_tenant(record):
    if not record.get("project_id") or not record.get("token"):
        raise ValueError("no tenant credentials; refusing to act as the platform")
    return RestClient(project=record["project_id"], token=record["token"],
                      host=SPACE)

def buy(record, number, webhook_url):
    client = as_tenant(record)
    bought = client.phone_numbers.create(number=number)
    client.phone_numbers.update(bought["id"], name=record["name"],
                                call_handler="relay_script",
                                call_relay_script_url=webhook_url)
    return bought
```

`RestClient(project, token, host)` builds its own `HttpClient`, whose session
carries that pair as basic auth (`rest/client.py`). Two clients in one process
are two identities. The tenant's requests are `GET
/api/relay/rest/phone_numbers/search`, `POST /api/relay/rest/phone_numbers`
with the required `number`, `PUT` and `DELETE` on
`/api/relay/rest/phone_numbers/{id}`.

3.0.1 wraps the tokens path as `client.project.tokens` but has no wrapper for
`POST /api/projects`, so that one request goes through `client._http`, the
shared `HttpClient` every namespace holds.

The spec documents no `GET` for tokens, so the value is read from the create
response and stored then. The response's `id` is stored beside it, because
`PATCH` and `DELETE /api/project/tokens/{token_id}` are how a credential is
rotated or revoked and nothing lists them. `tenants.json` stands in for the table where you keep
it. It holds a live credential, so it is in `.gitignore`; in your app that row
belongs in your database, encrypted.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # your project id, API token, space
python app.py onboard "Acme Dental"
python app.py offer "Acme Dental" 415
python app.py buy "Acme Dental" +14155550123 https://your-host/acme/
python app.py numbers "Acme Dental"
python app.py release "Acme Dental" <number_id>
```

The TypeScript surface is the same five commands on `@signalwire/sdk`:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start onboard "Acme Dental"
```

Your credentials must be a root project's. The spec says creating a project is
allowed only when authenticated as a top level project, and a subproject that
tries fails with `422 nested_subprojects_not_allowed`.

Buying a number is a billable action, so run `offer` first and buy a number you
mean to keep. There is no server to expose. The handler URL you pass to `buy`
is where inbound calls on that number will fetch their document.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier gives each client its own recorder and asserts the following.

- the recipe's permission list is the one the verifier expects, every value is in the spec's enum, `numbers` is in it and `management` is not
- onboarding sends `POST /api/projects` and `POST /api/project/tokens`, with the exact bodies, on the platform client
- the stored record carries the project id, the token and the token id, and survives as a file
- the spec documents `PATCH` and `DELETE` for a token id, and no `GET` that would list tokens
- a record with an empty token, or an empty project id, raises and builds no client
- the four clients built afterwards all carry the tenant's basic-auth pair and the space host
- the platform client, with every namespace recorded, sends no number request at all
- the tenant client sends the search, the purchase, the update, the list and the release, in that order, with documented paths, query params and bodies
- the `call_handler` sent is in the spec's `PhoneNumberCallHandlerRequest` enum
- `buy` returns the purchase response rather than the handler update that follows it
- the TypeScript surface sends the same requests, and each one carries the basic-auth pair it would go out with: the platform's for onboarding, the tenant's for all five number requests

## Limitations

The verifier proves who sends what, not what the platform allows. The spec
documents `401` on each of these operations for a request it will not
authenticate.

`numbers` reads one page. The list endpoint pages with `page_size` and
`page_token`. A tenant holding more numbers than one page needs the loop this
recipe does not write.

Releasing a number is not reversible, and the same number may not be available
to buy again. The create response for the subproject also carries a one time
`signing_key`, which this recipe does not keep.

## What to change first

Delete the `token` check in `as_tenant` and run the verifier. It stops at
"acted for a tenant with no credentials". That is the point: with the check
gone, `RestClient` falls back to the environment and sends the request as you.
