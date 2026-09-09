# Forward calls to a phone and keep the caller's number

> `connect` takes a `from`, which the schema calls "the caller ID to use when dialing the number". Set it to the inbound `call.from` and the phone that rings shows who really called, not the number they called.

**Scenario:** a one-person shop forwards the business line to a mobile and wants to see who is calling before picking up

## What this demonstrates

Plain forwarding has one flaw: the phone that rings sees the forwarding number,
so every call looks the same and callback means checking a log. This document
forwards with the caller's own number as the caller ID, so the mobile shows the
customer.

Two facts carry the claim.

- The vendored REST spec documents the inbound call webhook SignalWire sends
  when it fetches your document, and its `call` object requires `from`, "the
  number/URI that initiated this call".
- The bundled SWML schema's `connect` device takes `from`, described as "the
  caller ID to use when dialing the number", and a `timeout` that defaults to
  60 seconds.

The handler reads `call.from` and writes it back into `connect.from`. Nothing is
templated, so there is no question of which substitution syntax the platform
expands; the number the platform sent is the number the platform gets.

## How it works

```python
def document(caller):
    service = SWMLService(name="forward", route="/swml")
    connect = {"to": FORWARD_TO, "timeout": RING_FOR}
    if caller:
        connect["from"] = caller
    service.add_verb("connect", connect)
    return json.loads(service.render_document())
```

What a call from +1 415 555 0123 gets back:

```json
{"version": "1.0.0",
 "sections": {"main": [{"connect": {"to": "+15550100001",
                                    "timeout": 25,
                                    "from": "+14155550123"}}]}}
```

There is no `answer` verb. `connect` bridges the caller to the ringing phone
when it picks up, so the caller hears ringing rather than a picked-up line with
silence behind it. A call with no caller id leaves `from` out, and the platform
presents its own default rather than an empty string.

Passing a caller's number through as your caller ID is subject to the rules of
the country and carrier the call leaves through. The recipe shows the
mechanism. Whether your numbers may present it is a question for your carrier
agreement.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, basic auth, FORWARD_TO
python app.py                    # serves POST /swml on :8080
```

The TypeScript surface is the same handler on `@signalwire/sdk`'s
`SWMLService` with `node:http`, on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point the business number's call handler at `https://user:pass@your-host/swml`,
set `FORWARD_TO` to the mobile, and call the business number.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the Flask route with payloads shaped like the spec's
inbound call webhook and asserts the following.

- the spec requires `from` on the inbound call, and the sample payload carries every required field
- a call from a number renders exactly one `connect`, with `to` the forwarding target, `from` that number and the ring timeout, and it validates
- a request with no caller id renders the same `connect` with no `from` key at all
- the schema describes `connect.from` as the caller ID to use when dialing, and defaults `timeout` to 60
- a request without credentials is a 401
- the TypeScript surface, on a real port, returns the same two documents and the same 401

## Limitations

The verifier proves the document, not the display. Whether the mobile shows the
caller's number depends on the carriers between the platform and that phone.

The forwarding target is one number. Ringing several, in order or at once, is
[Dial destinations in order or all at once](../try-destinations-in-order/). The
`from` shown here applies to each of its devices.

## What to change first

Change `connect["from"] = caller` to `connect["from"] = FORWARD_TO` and run the
verifier. The document validates and the assertion fails, which is the point.
The schema accepts any caller ID; only the verifier says it must be the caller's.
