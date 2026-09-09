# Verify a caller ID for outbound calls

> Three REST requests register a number you own elsewhere as a verified caller ID. You submit the code you heard, and redial the verification call if you missed it.

**Scenario:** a shop that wants outbound calls to show its long-standing mobile number

## What this demonstrates

You send three requests. `POST /api/relay/rest/verified_caller_ids` carries
the number and a display name; the vendored REST spec titles it "Create
verified caller ID". `PUT /api/relay/rest/verified_caller_ids/{id}/verification`
carries `verification_code`, titled "Validate verification code". `POST` to
that same path is "Redial verification call". The SDK wraps the three as
`create`, `submit_verification` and `redial_verification` on
`client.verified_callers`.

The verifier checks the three requests against that spec. It marks `number` as
the one required field on create and `verification_code` as required on the
PUT. The spec's response schema carries `id`, `number`, `name`, `verified`,
`verified_at` and `status`.

## How it works

```python
client = RestClient()

def start(number, name):
    return client.verified_callers.create(number=number, name=name)

def confirm(caller_id, code):
    return client.verified_callers.submit_verification(caller_id, verification_code=code)

def resend(caller_id):
    return client.verified_callers.redial_verification(caller_id)
```

What the platform receives, in order:

```json
POST /api/relay/rest/verified_caller_ids
{"number": "+15557654321", "name": "Shop mobile"}

PUT  /api/relay/rest/verified_caller_ids/<id>/verification
{"verification_code": "482913"}

POST /api/relay/rest/verified_caller_ids/<id>/verification
```

The id in the second and third paths is the `id` the first response returned,
per the spec's response schema. `verified` and `status` in that schema are how
you read the outcome.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py start +1XXXXXXXXXX "Shop mobile"     # the phone rings and reads a code
python app.py confirm <id> <code>
python app.py resend <id>                          # if nobody caught the code
```

Use a number you can answer. There is no server to expose; each command speaks
to the REST API and exits.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls your three
helpers, and asserts the following.

- `start` makes one `POST` to the documented path with exactly `number` and `name`
- `confirm` makes one `PUT` to the id's verification path with exactly `verification_code`
- `resend` makes one `POST` to that verification path with no body
- every body field is documented and every required field is present, per the vendored spec
- the spec's required list for create is exactly `number`

## Limitations

The verifier proves the three requests. Whether the phone rings, what the code
is, and when `verified` flips are the platform's side of a live run.

## What to change first

Remove `name=name` from `start` and run the verifier. The exact-body assertion
fails, though the spec would still accept the request: `name` is optional and
`number` is the only required field.
