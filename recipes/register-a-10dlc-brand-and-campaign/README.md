# Register a 10DLC brand and campaign

> A brand and campaign are registered over REST, numbers are assigned to the campaign, and the status webhook reports carrier approval.

**Scenario:** a retailer that wants to text order updates from local numbers

## What this demonstrates

US carriers require A2P traffic from local (10-digit) numbers to come from a
registered brand (the business) and campaign (the use case and sample
messages). Both are REST resources here, so registration can be part of your
onboarding code rather than a form someone fills in. Approval is asynchronous,
measured in days rather than seconds, and each state change arrives at
`status_callback_url`.

## How it works

Three requests in dependency order:

```python
brand    = client.registry.brands.create(name=..., company_name=..., ein=..., legal_entity_type="PRIVATE_PROFIT",
                                         company_vertical="RETAIL", ..., status_callback_url=STATUS_URL)
campaign = client.registry.brands.create_campaign(brand["id"], sms_use_case="ACCOUNT_NOTIFICATION",
                                         description=..., sample1=..., sample2=..., opt_in_message=...,
                                         opt_out_message=..., help_message=..., status_callback_url=STATUS_URL)
order    = client.registry.campaigns.create_order(campaign["id"], phone_numbers=[...], status_callback_url=STATUS_URL)
```

The field lists come from the Campaign Registry reference:

- **brand**: legal entity, EIN, vertical, contacts
- **campaign**: use case, a 40+ character description, two to five 20+
  character samples, the opt-in/opt-out/help messages and keywords, and the
  content flags

Numbers can be assigned within about a day of campaign approval; brand *edits* after
submission go through Support.

What this does not cover: toll-free numbers use a verification form instead of
10DLC, and short codes go through sales. See
`get-toll-free-messaging-verified`. Opt-out handling on the numbers is yours:
`handle-opt-outs-yourself`.

## Run it

```bash
cd python
pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... PUBLIC_URL=https://<your-host>
python app.py                      # webhook receiver for status changes
python app.py register +1555... +1555...   # in another shell; edit BRAND/CAMPAIGN first
```

Brands carry a registration fee and campaigns a monthly fee, so read the numbers
in the Dashboard before running this against a real project.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, `register()` must make exactly three documented requests
in order. The verifier asserts:

- the campaign is created under the returned brand id
- the order is created under the returned campaign id, with our numbers and
  callback
- brand and campaign fields match the documented reference lists (the OpenAPI
  spec publishes no body schema for them)
- the webhook records state by resource id

## What to change first

Fill `BRAND` and `CAMPAIGN` with your real details, then wire the approved
campaign's numbers into `send-an-sms`.
