# Redact a message body after sending

> One PATCH with `body: ""` clears a sent message's stored body in SignalWire's records. The empty string is the only value the spec accepts, and only a message in a terminal state is eligible.

**Scenario:** you texted a one-time code and want it gone from SignalWire's stored records

## What this demonstrates

`PATCH /api/messaging/messages/{message_id}` with `{"body": ""}` redacts the body
of a message you already sent. The vendored REST spec says the endpoint "clears
the message body for compliance, privacy, or moderation purposes". It says "the
only accepted value for `body` is an empty string", and the platform rejects
anything else with `body_must_be_empty`. Per the spec, messages still `queued`
or `initiated` "cannot be redacted", while `delivered`, `undelivered` and
`failed` "are eligible". Once redacted, "the original body is overwritten and
cannot be recovered".

The SDK's REST client wraps no method for this path in 3.0.1. The recipe sends
the request through the `HttpClient` that `RestClient` builds once and shares
with every namespace (`signalwire/rest/client.py:74-85`).

## How it works

```python
client = RestClient()
http = client._http

def redact(message_id):
    return http.patch(f"/api/messaging/messages/{message_id}", body={"body": ""})
```

What the platform receives:

```
PATCH /api/messaging/messages/7c9e6679-7425-40de-944b-e07fc1f90ae7
{"body": ""}
```

The spec says the id is "the message segment ID", the one the create endpoint
returned and `/api/messaging/logs` shows. The spec's 200 response carries the
message with `body`, `status`, `direction`, `from`, `to` and `created_at`.

Pair this with a status callback. Redact when the callback reports a terminal
state, because the spec refuses the PATCH while the message is in progress.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py <message_id>
```

There is no server to expose; the script speaks to the REST API and exits. Take
the id from the send response of a message the platform has already delivered.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls `redact`, and
asserts the following.

- exactly one `PATCH` to the documented path for the id, with the body `{"body": ""}`
- the spec documents the path and body, and its required list is exactly `body`
- the spec's description of `body` says it must be an empty string
- the spec's description of the operation says it clears the body and that the original cannot be recovered
- that description puts `queued` and `initiated` on the refused side and `delivered`, `undelivered` and `failed` on the eligible side
- the spec's 200 response schema carries `id`, `body`, `status`, `direction`, `from`, `to` and `created_at`

## Limitations

The verifier proves the request. Whether a given message is eligible depends on
its state at the moment you send the PATCH.

Redaction changes SignalWire's copy. It cannot recall a copy the carrier
already delivered to a handset.

## What to change first

Change `{"body": ""}` to `{"body": "[redacted]"}` and run the verifier. The body
assertion fails, and on a live call the platform would answer
`body_must_be_empty`: this endpoint clears, it does not edit.
