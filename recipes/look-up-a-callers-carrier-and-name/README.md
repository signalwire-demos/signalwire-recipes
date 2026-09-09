# Look up a caller's carrier and name

> One GET returns a number's validity, formatting, country and type. `include=carrier,cnam` adds the carrier record and the caller-ID name.

**Scenario:** a support line that wants to know who is calling before the agent picks up

## What this demonstrates

`GET /api/relay/rest/lookup/phone_number/{e164}` returns what the platform knows
about a number. The vendored REST spec describes `include` as "further number
information to include in the response, some of which are billable". It takes
two values, joined by a comma: `carrier` for "full carrier information" and
`cnam` for "Caller ID information". The SDK wraps the call as
`client.lookup.phone_number(e164, **params)`.

## How it works

```python
client = RestClient()

def enrich(e164):
    return client.lookup.phone_number(e164, include="carrier,cnam")

def check(e164):
    return client.lookup.phone_number(e164)
```

What the platform receives:

```
GET /api/relay/rest/lookup/phone_number/+15557654321?include=carrier,cnam
```

The spec's response schema carries `valid_number`, `e164`, the national and
international formatted forms, `country_code`, `timezones` and `number_type`,
plus two objects you ask for with `include`. `carrier` holds `lrn`, `spid`,
`ocn`, `lata`, `city`, `state`, `jurisdiction`, `lec` and `linetype`; `cnam`
holds `caller_id`. `check` leaves `include` off, so it requests neither of
the two extras the spec marks as possibly billable.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py +1XXXXXXXXXX
```

There is no server to expose; the script speaks to the REST API and exits.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder, call both helpers, and assert
the following.

- `enrich` makes exactly one `GET` to the documented lookup path for the number with `include=carrier,cnam` and nothing else
- `check` then makes exactly one `GET` to the same path with no query
- the spec documents the path and the `include` parameter, and its description of `include` names `carrier` and `cnam`
- the spec's response schema carries every field this README names: the top-level ones, all nine under `carrier`, and `caller_id` under `cnam`

## Limitations

The verifier proves the request and the documented response shape, not what a
lookup returns for a real number. The spec says the included information is
"some of which are billable"; it does not price it.

## What to change first

Change `include="carrier,cnam"` to `include="carrier"` and run the verifier.
The params assertion fails, which is the point: `include` names exactly the
extra information you asked for.
