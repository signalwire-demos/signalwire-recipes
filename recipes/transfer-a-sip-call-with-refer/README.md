# Transfer a SIP call with REFER

> `calling.refer` is, in the spec's own command table, "Transfer a SIP call via SIP REFER". It takes a device of the one documented type and a `sip:` destination.

**Scenario:** a PBX wants the desk phone itself to complete the transfer rather than bridging a second leg

## What this demonstrates

There are two ways to move a call that came in over SIP. `calling.transfer`
sends it to a new destination through the platform. `calling.refer` sends a SIP
REFER instead, which is the SIP protocol's own transfer.

The vendored REST spec, `tools/openapi/rest.json`, is the authority for the
shape.

- `calling.refer` requires `device`, and the device requires both `type` and
  `params`.
- The device type enum holds exactly one value, `sip`.
- The SIP params require `to`, which "must start with `sip:`". `from` is
  optional and "must start with `sip:` when provided".
- `username` and `password` are there for a far end that challenges the REFER.
- `status_url` "receives refer lifecycle webhooks".

The recipe checks both URIs itself, so a `tel:` number or a `sips:` URI stops
in your code rather than at the API.

## How it works

```python
def refer(call_id, to, from_uri=None, status_url=None):
    params = {"to": _sip_uri(to, "to")}
    if from_uri:
        params["from"] = _sip_uri(from_uri, "from")
    if SIP_USERNAME and SIP_PASSWORD:
        params["username"] = SIP_USERNAME
        params["password"] = SIP_PASSWORD
    body = {"device": {"type": DEVICE_TYPE, "params": params}}
    if status_url:
        body["status_url"] = status_url
    return client.calling.refer(call_id, **body)
```

What the platform receives:

```json
{"command": "calling.refer",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"device": {"type": "sip",
                       "params": {"to": "sip:desk-2@pbx.example.com",
                                  "from": "sip:queue@pbx.example.com",
                                  "username": "…",
                                  "password": "…"}},
            "status_url": "https://your-pbx/refer-events"}}
```

The credentials come from the environment, so they are never literals in the
code the page shows. Leave them unset and both keys are absent.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py refer <call_id> sip:desk-2@pbx.example.com
```

The TypeScript surface is the same command on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start refer <call_id> sip:desk-2@pbx.example.com
```

The call has to be a SIP call for a REFER to mean anything. Take the call id
from a status callback or a tool webhook, and point `status_url` at a route of
yours if you want the lifecycle events.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, refers twice, and
asserts the following.

- a `tel:` destination and a `sips:` from both raise before any request is made
- `calling.refer` requires `device`, and the device requires `type` and `params`
- the device type enum is exactly `["sip"]`, and the recipe's value is in it
- the SIP params require `to`, whose description carries the `sip:` rule, and `from` carries the same rule for when it is present
- `username`, `password` and `status_url` are documented
- the spec's command table row for `calling.refer` says what the README says it says
- the first body carries the optional `from` and `status_url`, the second carries neither, as absent keys
- the TypeScript surface sends those same two bodies and refuses the same URIs

## Limitations

The verifier proves the request, not the transfer. Whether the far end accepts
a REFER, and what it does with it, belongs to that endpoint and its
configuration.

The spec documents no `to` for a non-SIP destination here. Moving a call to a
phone number is `calling.transfer`, in
[End or transfer a live call over REST](../end-or-transfer-a-live-call-over-rest/).

## What to change first

Change `DEVICE_TYPE` to `"pstn"` and run the verifier. The enum assertion
fails, which is the point: the spec documents one device type for a REFER, and
a second one would be an invention.
