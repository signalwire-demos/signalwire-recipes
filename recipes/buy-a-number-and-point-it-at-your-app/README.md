# Buy a number and point it at your app

> Search by area code or pattern, purchase, and assign the number's call handler, all over REST.

**Scenario:** provisioning a local number for each new tenant of a SaaS product

## What this demonstrates

Numbers are a REST resource. Three calls take you from nothing to a number that dials your code. Search inventory
by area code, region, city or digit pattern; purchase the number; set its call handler
to a SWML URL. No Dashboard step,
so it can run inside your own onboarding flow.

## How it works

```python
client.phone_numbers.search(areacode="415", number_type="local", max_results=5)   # GET  /api/relay/rest/phone_numbers/search
client.phone_numbers.create(number="+14155550123")                                 # POST /api/relay/rest/phone_numbers
client.phone_numbers.update(number_id, call_handler="relay_script",                # PUT  /api/relay/rest/phone_numbers/{id}
                            call_relay_script_url="https://<your-host>/ivr")
```

`call_handler: relay_script` with `call_relay_script_url` routes inbound calls
to a SWML document, the same thing the Dashboard's "SWML webhook" handler
does. The other handlers on the same field route to a Relay topic, a cXML URL,
or a Dialogflow agent; `message_handler` fields do the same for SMS. Lookup
(carrier and CNAM) is a sibling call on the same namespace. See
`look-up-a-callers-carrier-and-name`.

Purchasing is billable and immediate. Releasing is `DELETE` on the same
resource.

## Run it

```bash
cd python
pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=...
python app.py search 415
python app.py buy +14155550123 https://<your-host>/ivr
```

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer replaced by a recorder, `provision()` must make exactly three
requests in order:

- `GET` search, then `POST` purchase, then `PUT` update
- each checked against `tools/openapi/rest.json` for path, method, documented
  fields and required fields
- the URL the number is pointed at is the one passed in

## What to change first

Point the number at the `build-an-ivr-menu` document, then add
`register-an-e911-address-for-a-number` before the number takes real calls.
