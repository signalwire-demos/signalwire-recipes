# End or transfer a live call over REST

> Three call commands address a live call by id. `calling.end` hangs up with a reason from a fixed list, `calling.transfer` sends the call to a new destination, and `calling.disconnect` unbridges two connected calls.

**Scenario:** your agent desktop has a Hang up button and a Transfer box, and the call was not started by that page

## What this demonstrates

`POST /api/calling/calls` takes a `command`, the call `id` at the top level,
and a `params` object. Any process that holds a call id can steer the call,
whether or not it placed the call. The id arrives in an AI agent's tool
webhook, in a status callback, or in the response to a `dial`. The vendored
REST spec, `tools/openapi/rest.json`, documents three commands for ending or
moving a call.

- `calling.end` takes a `reason`: one of `hangup`, `cancel`, `busy`, `noAnswer`,
  `decline` or `error`. The recipe refuses any other value before it is sent.
- `calling.transfer` requires `dest`, which the spec describes as "a SIP URI,
  phone number, SWML URL, or an inline Calling SWML document".
- `calling.disconnect` has no params. The spec's command table describes it as
  "Disconnect bridged calls without hanging up either leg", so it separates two
  connected calls and ends neither.

The verifier proves the three requests. The spec is the authority for what the
platform does with them.

## How it works

```python
client = RestClient()

def hang_up(call_id, reason="hangup"):
    if reason not in END_REASONS:
        raise ValueError(...)
    return client.calling.end(call_id, reason=reason)

def transfer(call_id, dest):
    return client.calling.transfer(call_id, dest=dest)

def unbridge(call_id):
    return client.calling.disconnect(call_id)
```

What the platform receives for `transfer`:

```json
{"command": "calling.transfer",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"dest": "sip:tier2@pbx.example.com"}}
```

The SDK's `calling` namespace, `rest/namespaces/calling.py`, sends every call
command to that one path and puts the call id in `id`. The TypeScript SDK,
`@signalwire/sdk`, does the same: `client.calling.end(callId, { reason })`
produces the body above, which is what the verifier checks. The spec marks
`command`, `id` and `params` required on all three commands. `dest` accepts a
string or an object. An object carries an inline SWML document, for when the
new leg needs a document of its own.

A transfer over REST is different from `connect` inside a SWML document. The
document bridges a call it is already running. The REST command moves a call
from outside, which is what a supervisor console or a CRM needs.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py end <call_id> busy
python app.py transfer <call_id> sip:tier2@pbx.example.com
python app.py disconnect <call_id>
```

The TypeScript surface is the same three commands on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start end <call_id> busy
```

Take the call id from a tool webhook, a status callback, or the `dial`
response. There is no server to expose; the script speaks to the REST API and
exits.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the three helpers,
and asserts the following.

- a reason outside the enum raises before any request is made
- each helper adds exactly one `POST` to the documented calling path
- the spec marks `command`, `id` and `params` required on each of the three commands
- the `calling.end` reason enum is exactly the six values, and the recipe's own list matches it
- each of the six reasons reaches the wire, and the default is `hangup`
- the spec's command table row for each of the three commands says what the README says it says
- `calling.transfer` requires `dest`, and the spec accepts a string or an object for it
- `calling.disconnect` documents no params, and the sent params are empty
- each body equals the expected `{"command", "id", "params"}` shape, and every param is a documented property
- the TypeScript surface, driven through the same recorder seam, sends those same three bodies, refuses the same undocumented reason, and puts all six reasons on the wire

## Limitations

The verifier proves the request, not the call's fate. Whether a `dest` answers,
and what the far end hears for each `reason`, are live behaviour.

`calling.disconnect` presumes a bridge exists. On a call with no peer leg the
platform's response, not the recipe, says what happens.

## What to change first

Change `"busy"` in the verifier's first helper call to `"rejected"`. The recipe
raises before the request, which is the point. The six reasons are the whole
vocabulary, and the check sits in your code rather than in a 400.
