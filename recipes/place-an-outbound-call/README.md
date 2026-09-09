# Place an outbound call

> One POST originates the call and carries the document it runs.

**Scenario:** a bike shop telling a customer their repair is ready

## What this demonstrates

Your backend decides a call should happen, and one request makes it happen. The same
request carries the SWML the call runs once someone picks up. There is no second
fetch, and no URL of yours to keep online for it.

The reverse of `answer-an-inbound-call`: there the platform came to you, here
you go to the platform.

## How it works

`client.calling.dial()` posts a `dial` command to `/api/calling/calls`. It takes
either `url` or `swml`, and the choice is about whether the call needs anything
looked up.

```python
client.calling.dial(**{
    "from": FROM,
    "to": to,
    "swml": reminder_document(message),
    "status_url": f"{PUBLIC_URL}/call-status",
    "status_events": ["ringing", "answered", "ended"],
    "timeout": 25,
})
```

`url` makes the platform fetch a document from you when the call connects, which
is what you want when the greeting depends on who answered. `swml` puts the
document in the request itself. A reminder has nothing to look up, so it travels
inline and no server is involved after the POST returns.

`from` is a Python keyword, so the parameters go in through a dict rather than
as keyword arguments.

`timeout` is the ring timeout, documented as 1 to 600 seconds. Leaving it at the
default is how outbound calls end up talking to voicemail: 25 seconds stops
ringing while a person could still plausibly answer.

The call's lifecycle goes to `status_url`, filtered by `status_events`. The
documented events are `created`, `ringing`, `answered` and `ended`. Receiving
them is `handle-call-status-callbacks`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # add your credentials and From number
python app.py +15552223333
```

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer replaced by a recorder, `place()` must make exactly one
request. The verifier asserts:

- one POST to `/api/calling/calls` with `command: dial`
- every parameter is a documented property of the SWML dial variant, and its
  required fields are present, read from `tools/openapi/rest.json`
- the document travels as `swml`, with no `url` alongside it
- that document is itself valid SWML, so the call has something real to run
- `status_events` uses only the four documented event names
- `timeout` is inside the documented range

## Limitations

An inline document is fixed at dial time. Anything that depends on who picked up
belongs behind `url`, where you answer with a document built for that call.

`dial` accepting the request does not mean anyone answered. Busy, no-answer and
failed all arrive later on `status_url`, which is why the recipe sets one.

## What to change first

Swap `swml` for `url` and point it at the route from `answer-an-inbound-call`.
The call behaves the same and the document now comes from your server, which is
the trade this parameter is making.
