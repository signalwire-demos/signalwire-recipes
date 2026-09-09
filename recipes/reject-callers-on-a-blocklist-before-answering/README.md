# Reject callers on a blocklist before answering

> The inbound call webhook carries `call.from`. A listed number gets a document that is one `hangup` with a reason and no `answer`, so the call is refused before it is picked up. Everyone else gets `answer` and `connect`.

**Scenario:** a shop keeps getting the same robocaller and wants those numbers refused without a human hearing them ring

## What this demonstrates

Call screening does not need a feature. SignalWire fetches your document with
the inbound call webhook, and that request carries the caller's number, so
your handler is the place where the decision lives. The list is yours, kept
wherever you keep things, and the platform never sees it.

Two facts carry the claim.

- The vendored REST spec documents the inbound call webhook payload. Its `call`
  object requires `from`, "the number/URI that initiated this call", and that
  is what the handler reads.
- The bundled SWML schema's `hangup` verb takes an optional `reason` whose
  values are exactly `hangup`, `busy` and `decline`. A document that starts
  with `hangup` and never says `answer` refuses the call rather than picking it
  up and dropping it.

Numbers are compared by digits, so `+1 (555) 555-0101` on the list still
catches `15555550101` on the wire. An absent caller id is not on any list and
is connected.

## How it works

```python
def is_blocked(caller):
    d = digits(caller)
    return bool(d) and d in BLOCKED

def document(caller):
    service = SWMLService(name="screen", route="/swml")
    if is_blocked(caller):
        service.add_verb("hangup", {"reason": REASON})
    else:
        service.add_verb("answer", {})
        service.add_verb("connect", {"to": DESTINATION})
    return json.loads(service.render_document())
```

What a listed caller's request gets back:

```json
{"version": "1.0.0", "sections": {"main": [{"hangup": {"reason": "decline"}}]}}
```

`decline` tells the network the call was refused. `busy` makes the line look
engaged instead, which a persistent dialler reads as a dead end. Both are in
the schema; `REJECT_REASON` picks one.

The route sits behind the basic auth you put in the webhook URL, as every
document-serving recipe here does. Nobody but SignalWire reads your routing.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, basic auth, DESTINATION
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

Point a number's call handler at `https://user:pass@your-host/swml` and call it
from a listed number and from another. Edit `BLOCKLIST` for your own.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the Flask route with payloads shaped like the spec's
inbound call webhook and asserts the following.

- the sample payload carries every field the spec requires on `call`, and no field the spec does not know
- a listed number, and the same number in a different format, each get a document of exactly one verb, `hangup` with `reason: decline`, and it validates
- an allowed number, and a request with no caller id, each get `answer` then `connect` to the destination, and it validates
- the schema's `hangup.reason` allows exactly `hangup`, `busy` and `decline`, and the recipe's reason is one of them
- a request without credentials is a 401
- the TypeScript surface, on a real port, returns the same four documents and the same 401

## Limitations

The verifier proves the documents, not what a blocked caller hears. What
`decline` and `busy` sound like on the far end depends on the caller's carrier.

`call.from` is what the network delivered. A caller who withholds their number
arrives with none, and this recipe connects them; screening anonymous callers
is a policy you add, not a default.

## What to change first

Add `"+14155550123"` to `BLOCKLIST` and run the verifier. The allowed caller's
assertion fails on a `hangup`, which is the point: the list is the whole
decision, and it is yours.
