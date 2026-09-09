# Look up the caller and branch inside the call flow

> The call asks your API who is calling. `request` with `save_variables` true parses the JSON into `request_response.<field>`, `switch` branches on one of those fields, and a `cond` around it still reaches a human when the lookup fails.

**Scenario:** a bike shop routes a known customer to their own desk and everyone else to the main line

## What this demonstrates

Routing on data usually means a server of yours in the call path: SignalWire
fetches a document from you, you call your database, you answer. The `request`
method removes that hop. The hosted document calls your API itself, and the
next verb reads the answer.

Three parts. `request` sends the caller's number to your endpoint and, with
`save_variables` true, parses the JSON reply into variables. `switch` then
branches on `request_response.tier`, one of those parsed fields. Around both, a
`cond` checks `request_result`, so a CRM that is slow or down sends the call to
the main line instead of dropping it.

## How it works

```python
service.add_verb("request", {
    "url": CRM_URL, "method": "POST",
    "headers": {"Content-Type": "application/json",
                "Authorization": f"Bearer {CRM_TOKEN}"},
    "body": {"phone": "%{call.from}"},
    "save_variables": True,          # parse the reply into request_response.*
    "connect_timeout": 3, "timeout": 5,
})

main = service.get_document()["sections"]["main"]
main.append({"cond": [
    {"when": "request_result == 'success'",
     "then": [{"switch": {"variable": "request_response.tier",
                          "case": {"gold": [gold_leg], "standard": [standard_leg]},
                          "default": [standard_leg]}}]},
    {"else": [{"play": {"url": f"say:{APOLOGY}"}}, standard_leg]},
]})
```

The [request reference](https://signalwire.com/docs/swml/reference/calling/request.md)
describes `save_variables` as "Store parsed JSON response as variables" and
gives `request_result` as "Either `success` or `failed`". It references a saved
field as `${request_response.<field>}`. `switch.variable` takes the name on its
own, the way the IVR recipes pass `prompt_value`.

Two defaults are worth changing. `timeout` and `connect_timeout` are both `0`,
meaning no timeout, so a hung CRM would hold the call open. This document sets
five and three seconds and then handles the failure.

`cond` takes an array, and `add_verb` takes a dictionary, so `add_verb("cond",
[...])` returns `False` and adds nothing. The array is appended to the document
instead. `get_document()` hands back the live document, so the `hangup` added
after it still lands last. Every other verb goes through `add_verb`, which
validates it against the bundled schema as it is added.

The whole document is hosted as a Call Flow, the same `relayml` and `flow_data`
pair `build-an-ivr-without-a-server` uses, so nothing of yours is in the call.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # credentials, CRM_URL, CRM_TOKEN, the two desks
python app.py deploy             # prints the call flow's resource id
python app.py point <resource_id> +15551230000
```

The TypeScript surface builds the same document on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start deploy
npm start point <resource_id> +15551230000
```

Your endpoint has to answer a POST of `{"phone": "+1..."}` with JSON carrying a
`tier`. Call the number from a phone your CRM knows.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier builds the document and drives the REST calls through a recorder.
It asserts the following.

- the document validates and its verbs are `answer`, `request`, `cond`, `hangup`, in that order
- the `request` carries the CRM URL, the bearer header, `{"phone": "%{call.from}"}`, `save_variables` true and both timeouts
- the `cond` is a `when` on `request_result` whose `then` is the `switch` on `request_response.tier` with a case per desk and a default, and an `else` that plays the apology and still connects
- the schema requires `url` and `method` on `request`, `when` and `then` on a cond branch, `else` on the last, and `variable` and `case` on `switch`; its variable pattern accepts `${...}` and `%{...}`
- `save_variables` is described as storing the parsed JSON, and both timeouts default to `0`
- `add_verb` returns `False` for the list-shaped `cond` and raises for a `request` with no `url`, leaving the document unchanged
- the flow is created with `title`, the document as `relayml` and its paired `flow_data`, then the number is looked up by exact match and bound with `handler: calling`, all three documented against the vendored spec
- the TypeScript surface builds the same document and sends the same three requests

## Limitations

The verifier proves the document and the requests. Whether the platform
substitutes `%{call.from}` into the body and resolves
`request_response.tier` at runtime is live behaviour, described in the request
reference and not asserted here.

Your endpoint is in the call path even though your call server is not. Its
latency is the caller's silence, which is what the two timeouts bound.

The record is fetched once, at the start. A branch that needs fresh data later
in the call makes a second `request`; each one overwrites `request_response`.

## What to change first

Delete `save_variables` and run the verifier. The document still validates,
because the field is optional, and the assertion fails. On a real call the
`switch` would find no `request_response.tier` and take its default, so every
caller reaches the main line and nothing errors.
