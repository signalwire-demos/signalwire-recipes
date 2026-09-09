# Register an E911 address for a number

> Two POSTs and one GET create an emergency address with the nine fields the spec requires. They look up the number's id and attach the new address to the number.

**Scenario:** a US workshop that puts its street address behind the number its staff dial out on

## What this demonstrates

`POST /api/relay/rest/addresses` creates the address. The vendored REST spec
requires `label`, `country`, `first_name`, `last_name`, `street_number`,
`street_name`, `city`, `state` and `postal_code`. It takes `emergency_enabled`,
`auto_correct_address`, `address_type` and `address_number` as options. `POST
/api/relay/rest/phone_numbers/{id}/e911_address` with `e911_address_id` attaches
the address to a number.

The SDK wraps the first call as `client.addresses.create`. Its addresses
namespace, `signalwire/rest/namespaces/addresses.py`, has no method for the
attach path in 3.0.1. The recipe sends that request through the `HttpClient`
that `RestClient` builds once and hands to every namespace
(`signalwire/rest/client.py:74-85`).

## How it works

```python
def number_id(e164):
    for item in client.phone_numbers.list().get("data", []):
        if item.get("number") == e164:
            return item["id"]

def attach(phone_number_id, address_id):
    return client.addresses._http.post(
        f"/api/relay/rest/phone_numbers/{phone_number_id}/e911_address",
        body={"e911_address_id": address_id})

def register(e164, **address):
    created = create_address(**address)          # the nine required fields, emergency_enabled on
    return attach(number_id(e164), created["id"])
```

What the platform receives:

```json
POST /api/relay/rest/addresses
{"label": "Ridgeline Cycles workshop", "country": "US",
 "first_name": "Dana", "last_name": "Whitfield",
 "street_number": "1200", "street_name": "Harbor Way", "address_type": "Suite",
 "address_number": "4", "city": "Portland", "state": "OR", "postal_code": "97209",
 "emergency_enabled": true}

POST /api/relay/rest/phone_numbers/<number id>/e911_address
{"e911_address_id": "<address id>"}
```

The spec lists `address_type` as an enum: Apartment, Basement, Building,
Department, Floor, Office, Penthouse, Suite, Trailer or Unit. The number id is
the `id` of the phone number resource, not the number itself. `number_id` reads
it from `GET /api/relay/rest/phone_numbers` with the spec's `filter_number`
query, so a project with hundreds of numbers still answers on the first page.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python -c "import app; print(app.register('+1XXXXXXXXXX', label='<label>', first_name='<first name>', last_name='<last name>', street_number='<street number>', street_name='<street name>', city='<city>', state='<state>', postal_code='<postal code>'))"
```

Fill every placeholder with your own dispatchable US address and a US number on
your project. This creates an emergency location on your account, and a wrong
one is worse than none. `register` reads the `id` from the create response and
attaches it; the two halves are also callable on their own.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder. It answers the create with an id
and the numbers list with two numbers. You call `register` and assert the
following.

- the flow makes three requests in order: `POST` the addresses path, `GET` the numbers list with `filter_number` set to the number, `POST` the number's e911 path
- the spec's required set for the create is exactly the nine names the verifier expects
- the create body carries those nine, `emergency_enabled: true` and the three optional fields, and every field is documented
- the attach body is exactly `e911_address_id` with the id the create returned, which is the spec's whole required list for that call

## Limitations

The verifier proves the requests. Address validation, and whether the platform
accepts the address as an emergency location, happen on the live call to the
API.

There is no SDK method for the attach call in 3.0.1, so the recipe reaches for
the shared HTTP client. A later SDK may add a wrapper.

This recipe was written for US addresses and US numbers and enforces neither.
`country` defaults to `US`, the only value it was verified with; check the
spec's `emergency_enabled` behaviour before trying another.

## What to change first

Drop `postal_code` from the `create` body and run the verifier. The required-list
assertion fails, which is the point: the spec, not this recipe, decides what an
emergency address must carry.
