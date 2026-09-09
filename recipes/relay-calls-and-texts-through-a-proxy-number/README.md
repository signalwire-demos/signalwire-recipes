# Relay calls and texts through a proxy number

> Two people share one number of yours. A call from either to it becomes `connect` to the other with `from` set to your number; a text becomes a `reply` to the other from your number. Neither party ever sees the other's.

**Scenario:** a marketplace connects a buyer and a seller for one transaction without giving either the other's phone number

## What this demonstrates

Number masking is two lookups and two verbs. Your handler keeps a session that
says, on proxy P, participant A reaches B and B reaches A. When either of them
calls or texts P, the inbound webhook carries `from` and `to`, and the session
gives the other party. The document then relays the call or the text with P as
the visible number.

Three facts carry the claim.

- The inbound call webhook's `call` and the inbound message webhook's `message`
  both require `from` and `to`, which is all the lookup needs.
- The bundled schema describes `connect.from` as "the caller ID to use when
  dialing the number", so the called party's phone shows the proxy.
- `reply` is the Messaging SWML method that sends a message. Its `to` defaults
  to the sender and its `from` to the number that received the text, so naming
  both relays the text with the proxy on it.

A stranger who calls the proxy hears that the number is not active and the call
ends. A stranger who texts it gets an empty document: nothing sent, nothing
kept. Pairing two numbers is a decision about who can reach whom, so `/pair` is
behind a key the server holds and your systems present as `X-Proxy-Key`.

## How it works

```python
def call_document(caller, proxy):
    service = SWMLService(name="proxy-call", route="/call")
    other = other_party(proxy, caller)
    if other:
        service.add_verb("connect", {"to": other, "from": proxy})
    else:
        service.add_verb("answer", {})
        service.add_verb("play", {"url": f"say:{NOT_ACTIVE}"})
        service.add_verb("hangup", {})
    return json.loads(service.render_document())

def message_document(sender, proxy, body):
    other = other_party(proxy, sender)
    steps = []
    if other:
        steps.append({"reply": {"to": other, "from": proxy, "body": body or ""}})
    return {"version": "1.0.0", "sections": {"main": steps}}
```

What the buyer's call to the proxy gets back:

```json
{"version": "1.0.0",
 "sections": {"main": [{"connect": {"to": "+13105550199", "from": "+15550001111"}}]}}
```

The session store is a file keyed by proxy and participant, with both
directions written at once. In your app it is a table with an expiry, because
a masked pairing should end when the transaction does. The webhooks and the
pairing are different requests, which is why the store is not a dictionary.

Both webhook routes sit behind the basic auth you put in the handler URLs, as
every document-serving recipe here does.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, proxy number, auth, key
python app.py                    # serves POST /call, POST /message, POST /pair
```

The TypeScript surface is the same three routes on `@signalwire/sdk`'s
`SWMLService` with `node:http`, on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Buy a number and point its call handler at `https://user:pass@your-host/call`
and its message handler at `https://user:pass@your-host/message`. Then pair two
numbers:

```bash
curl -X POST https://your-host/pair -H "X-Proxy-Key: $PROXY_ADMIN_KEY" \
  -H "content-type: application/json" -d '{"a": "+14155550123", "b": "+13105550199"}'
```

Either party calls or texts the proxy and reaches the other.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the Flask routes with payloads shaped like the spec's two
inbound webhooks and asserts the following.

- `/pair` refuses a missing and a wrong key with 403 and writes nothing, and with the key writes both directions of the session
- after a module reload, a call from either party renders one `connect` to the other with `from` the proxy, and a stranger's call renders `answer`, a spoken not-active line and `hangup`
- a text from either party renders one `reply` to the other from the proxy carrying the body, and a stranger's text renders an empty document
- the call documents validate against the bundled schema, and the schema's description of `connect.from` is what this README quotes
- the message documents are checked against the documented Messaging method set instead, because the bundled schema is the Calling one, and `send_sms` is not in that set
- both webhook payloads carry every field the spec requires, and the spec requires `from` and `to` on each
- both webhook routes refuse an unauthenticated POST with 401
- re-pairing Alice with Carol removes Bob's route back to her: Bob's next call hears the not-active line and his text sends nothing
- the TypeScript surface, on a real port, pairs behind the same key, renders the same six documents, and returns the same 401s

## Limitations

A participant is in one pairing at a time on a given proxy. Pairing A with C
removes B's route back to A, or B could keep reaching A while A's replies went
to C. Two pairings for one person need two proxy numbers.

The verifier proves the documents, not the display. Whether a phone shows the
proxy number depends on the carriers between the platform and that phone.

Sessions here never expire. A real pairing has a lifetime, and the table that
replaces the file should carry one.

Presenting a number you own as the caller ID for a relayed call is the normal
case here; the proxy is yours. Relaying a text from a 10DLC number is A2P
traffic and needs a registered campaign.

## What to change first

Change `"from": proxy` to `"from": caller` in `call_document` and run the
verifier. The document validates and the assertion fails, which is the point:
that one field is the difference between a relay and a leak.
