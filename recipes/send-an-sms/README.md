# Send an SMS

> The three-line version, plus what to do when it fails.

## What this demonstrates

Sending a message is trivial. Handling the outcome is the part tutorials skip. A queued message is not a delivered
one, and carrier rejections arrive later on a status webhook rather than in the API
response.

## How it works

`RestClient().compat.messages.create(From=..., To=..., Body=..., StatusCallback=...)`
posts to the Compatibility Messages endpoint
(`/api/laml/2010-04-01/Accounts/<project>/Messages`). It returns as soon as the
message is *accepted*: `status` is `queued`. Delivery, failure and carrier
filtering arrive afterwards as POSTs to `StatusCallback` with `MessageSid`,
`MessageStatus` and, on failure, `ErrorCode`.

The webhook handler keys on `(MessageSid, MessageStatus)` and ignores a pair it
has already seen, so a carrier retry of `delivered` runs your side effect once.
Idempotency is your handler's job; the platform does not de-duplicate callbacks
for you.

Two other ways to send the same message: SWML `send_sms` from inside a call
(see `text-the-caller-during-the-call`), and `RelayClient.send_message` over a
RELAY WebSocket. The SDK's typed `RestClient` has no native `messages`
namespace in 3.0.x; the Compatibility endpoint is the supported REST path.

## Run it

```bash
cd python
pip install -r requirements.txt
python app.py
# in another shell, once PUBLIC_URL is reachable from SignalWire:
python -c "import app; print(app.send('+15552223333', 'Your table is ready.'))"
```

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It swaps the REST client's HTTP layer for a recorder, then checks the POST path and
fields against `tools/openapi/compat.json`. It drives the status webhook with
duplicate and non-terminal callbacks, and asserts the side effect fires exactly once
per terminal status.

## Limitations

A 201 means accepted, never delivered. Treat the status webhook as the source of
truth, and make the handler idempotent - it can fire more than once for the same
message.

## What to change first

Send to an invalid number and watch which failure surfaces synchronously versus on
the webhook.
