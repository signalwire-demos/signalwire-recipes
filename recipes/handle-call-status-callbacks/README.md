# Handle call status callbacks

> Asking for `initiated`, `ringing`, `answered` and `completed` in `StatusCallbackEvent` asks SignalWire to post those state changes of a call to your URL. Keyed by `CallSid` and ordered by `SequenceNumber`, the callbacks that arrive rebuild the call's life, with the duration when the completed one carries it.

**Scenario:** a shop that calls customers when repairs are done and wants a record of what happened to each call

## What this demonstrates

Storing each callback under its `CallSid` by `SequenceNumber` rebuilds an
ordered timeline of the call, whatever order the callbacks arrived in. The
compat call create takes `StatusCallback` and `StatusCallbackEvent`, and the
vendored spec describes the events as "Valid values: initiated, ringing,
answered, completed, ringing_forwarded, ringing_queued. Defaults to
`completed`". With a `StatusCallback` and no event list, you ask for only the
completed event. This recipe asks for four of the six; `ringing_forwarded` and
`ringing_queued` are the two it leaves out. The spec documents the payload it
posts. The voice status callback carries `CallSid`, `CallStatus`,
`SequenceNumber`, `Timestamp`, `Direction`, `From`, `To` and a block of audio
statistics. `CallDuration` is "Only present on the `completed` event", and the
spec does not require it there.

`SequenceNumber` is "The order in which events occur, starting at 0", and the
spec adds that events "may not appear" in that order at your server. So the
handler stores by sequence and never by arrival.

## How it works

```python
EVENTS = ["initiated", "ringing", "answered", "completed"]

def place(to):
    return client.compat.calls.create(To=to, From=FROM, Url=CALL_URL,
                                      StatusCallback=STATUS_URL,
                                      StatusCallbackEvent=EVENTS,
                                      StatusCallbackMethod="POST")

def record(payload):
    CALLS.setdefault(payload["CallSid"], {})[int(payload["SequenceNumber"])] = payload
```

What the platform receives:

```json
POST /api/laml/2010-04-01/Accounts/<project>/Calls
{"To": "+1555XXXXXXX", "From": "+1555YYYYYYY", "Url": "https://<your-host>/cxml/greeting.xml",
 "StatusCallback": "https://<your-host>/status",
 "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
 "StatusCallbackMethod": "POST"}
```

`timeline(call_sid)` sorts the stored payloads by sequence and returns the
steps, the final status, the parties, and the duration when the `completed`
callback carries `CallDuration`. `GET /calls/<CallSid>` serves it from the
process that holds the store. The fixture's third callback uses `CallStatus`
`in-progress`, which the spec's enum defines as "The call was answered and is
in progress".

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, CALL_FROM, CALL_URL, STATUS_CALLBACK_URL
python app.py                    # the handler, on port 8080
```

```bash
cd python                        # in another shell
python app.py +1XXXXXXXXXX       # place a call
```

The handler needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok, and set `STATUS_CALLBACK_URL` to `https://<your-host>/status`.
`CALL_URL` is what the spec calls "The URL to handle the call". Set it to a
URL that answers with valid cXML. Then read the life of the call from the
running server:

```bash
curl "https://YOUR_HOST/calls/CALL_SID"
```

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier swaps the SDK's HTTP layer for a recorder and drives the Flask app
with its test client. It asserts the following.

- `place` makes one `POST` to the documented compat calls path with exactly the expected body
- the four events it asks for are in the list the spec's description calls valid, and the two it leaves out are `ringing_forwarded` and `ringing_queued`
- the callback method is in the spec's enum
- each of four fixture callbacks carries every field the spec's voice status callback requires, no field it lacks, and a `CallStatus` from its enum
- the spec says `CallDuration` is only on the completed event and `SequenceNumber` starts at 0
- the four arrive in the order 3, 0, 2, 1, one of them form-encoded, and the handler answers each with `204`
- the timeline is initiated, ringing, in-progress, completed in sequence order, with the duration from the completed event and the parties from the payload
- all 24 arrival orders of the four callbacks give that same complete timeline, compared whole against one expected object
- a call with one `initiated` event has no duration yet, and an unknown call has an empty timeline
- a completed callback without `CallDuration` ends the timeline with `completed` and no duration
- `GET /calls/<CallSid>` on the server returns the same timeline as JSON

## Limitations

The spec calls status callbacks "advisory, best-effort notifications" whose
"delivery can be delayed or fail silently". It says not to gate time-critical
actions on receiving one. A timeline is a record, not a trigger.

The store is a dictionary in the process. Swap `CALLS` for your database before
anything depends on it.

## What to change first

Swap `CALLS` for a store of your own keyed by `CallSid` and `SequenceNumber`,
so a restart or a second worker keeps the same ordering. To see what that key
protects, as an exercise and not a change to keep: replace
`int(payload["SequenceNumber"])` in `record` with `len(CALLS[payload["CallSid"]])`
and run the verifier. The step-order assertion fails on the fixture's shuffled
arrival, which is the failure this recipe exists to prevent.
