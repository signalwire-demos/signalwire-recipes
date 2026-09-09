# Call the recipient when a text goes undelivered

> A message status callback reporting `undelivered` or `failed` carries the recipient and the body. One `POST /api/calling/calls` with inline SWML then speaks the same message to the same number, once per message id, and only when SignalWire signed the callback.

**Scenario:** a bike shop's pickup notice reaches a landline customer by voice when the text fails

## What this demonstrates

A text can fail quietly: a landline, a blocked number, a carrier rejection.
The status callback you set when sending says so, with `status` set to
`undelivered` or `failed`, and the spec requires `to` and `body` on that
payload. That is everything a follow-up call needs. The handler places one
call with the message spoken inline: `answer`, `play` a `say:` of the body,
`hangup`.

Three guards make it safe to run unattended, and each one is a way this
otherwise loses money.

## How it works

```python
FALLBACK_ON = {"undelivered", "failed"}

def spoken(body):
    """One line. A newline in the body would fail the play url's own pattern."""
    return "We could not reach you by text. The message was: " + " ".join(body.split())

def handle(event):
    if event.get("status") not in FALLBACK_ON:
        return {"called": False, "reason": str(event.get("status") or "none")}
    message_id, to = event.get("id"), event.get("to")
    if not message_id or not to:
        return {"called": False, "reason": "no message id" if not message_id
                else "no recipient"}
    if not claim(message_id):                 # atomic, before anything is spent
        return {"called": False, "reason": "already handled"}
    try:
        call = place_call(to, event.get("body") or "")
    except Exception:
        release(message_id)                   # nothing was placed, so let it retry
        raise
    return {"called": True, "call_id": str(call.get("id") or "")}
```

**The signature.** The route checks it before anything else, because a webhook
that spends money on any POST is an open invitation. The check is the one from
`verify-a-webhook-signature`: HMAC over the callback URL plus the raw body,
SHA-256 header preferred, hex compared in constant time. The URL is the
`status_callback` you configured, with the request's own query appended. The
configured query is stripped first, so a tagged URL like
`.../message-status?source=orders` is signed once rather than twice.

**The claim.** `claim()` creates one marker file per message id with `"x"`,
which is `O_EXCL`, so two deliveries arriving at once cannot both win it. It
runs before the dial, and the dial's failure releases it. The spec calls these
callbacks "advisory, best-effort notifications" whose "delivery can be delayed
or fail silently". The handler treats arrival as a hint, not a promise.

**The single line.** The bundled schema's `play_url` pattern is anchored and
its `.` does not match a newline, so a two-line body would render a document
the platform refuses. `spoken()` collapses whitespace, which is why a pickup
notice with an address on its own row still places a call.

`dial` with `swml` puts the whole call in the request, so nothing has to be
fetched from you when the callee answers. The spec's
`Calling.CallCreateParamsSWML` variant requires `from` and `swml`, and every
param this recipe sends is in its property list.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # credentials, signing key, VOICE_FROM, STATUS_URL
python app.py                    # serves POST /message-status on :8080
```

The TypeScript surface is the same handler with `node:http`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Send a text with `status_callback` set to `STATUS_URL` (the REST send in
`send-an-sms` shows where). Text a landline, and the phone rings.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The HTTP layer is replaced by a recorder and the marker directory sits in a
temp directory. The verifier posts seven signed callbacks and asserts the
following.

- `undelivered` places one dial: a documented POST whose params are all in the SWML variant and include its required `from` and `swml`
- the inline document validates and is `answer`, `play` of a `say:` carrying the body, `hangup`
- a body with a newline is spoken on one line, and the rendered `play` url carries no newline
- the marker for a message id already exists when its dial goes out, so the claim comes before the spend
- the same callback again places nothing and answers "already handled"
- `delivered`, `sent`, an event with no id and an event with no recipient each place nothing, with the reason naming why
- `failed` for a third message places a second call with its own body
- an unsigned callback, a bad signature, and an empty SHA-256 header beside a valid SHA-1 are all 403
- a SHA-256 signature is accepted, and so is a callback whose URL carries a query, signed over that query
- a query carrying an encoded space is accepted, so the signature is over the raw query and not a re-serialised one
- a dial whose response never arrives keeps its claim, so the same callback afterwards places nothing
- a `STATUS_URL` that already carries a query is signed once, on both surfaces
- the spec requires `id`, `status`, `to` and `body`, its status enum holds all four statuses used here, and it calls the callbacks advisory and best-effort
- the TypeScript surface places the same two calls, claims before it dials, and signs a tagged URL once
- a failed dial on the TypeScript surface answers 500 rather than ending the process, and the request after it is served and finds the claim

## Limitations

The verifier proves the requests, not the ring. Whether a call is answered,
and whether a machine picks up, is a live question; `detect-an-answering-machine`
is the next step for the machine case.

The customer sees `VOICE_FROM`, not the number that texted them. A voice call
needs a voice-capable number, and the two are often different; put a number
they recognise there.

The compat send (`StatusCallback`) posts a different payload, form-encoded,
with `MessageStatus`, `To` and `Body`. This handler reads the REST shape only;
the compat one is a field-name change in `handle`.

The marker directory is a stand-in for a unique key in your table, and it
never expires. A call placed for a message is a cost, so that key is the thing
to keep.

A dial whose response never arrives is not retried. A request that reached
SignalWire and lost its response looks like one that never arrived. The claim
stays, so at most one call goes out per message. The marker is where a
reconciler looks; `reconcile-webhooks-against-the-logs-api` finds out what
really happened.

## What to change first

Add `"sent"` to `FALLBACK_ON` and run the verifier. The `sent` row fails,
because a text that merely left the platform is not a text that failed. Every
recipient would get a phone call for a message still on its way.
