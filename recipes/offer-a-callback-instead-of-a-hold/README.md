# Offer a callback instead of a hold

> Let the caller go, then ring back already knowing why.

**Scenario:** a support queue that runs deeper than its staffing on a bad day

## What this demonstrates

A caller who has waited long enough is released with a promise rather than held
longer. When someone is free the call goes out, and it opens by naming what
they wanted. They do not explain it twice.

The design is forced by a constraint worth knowing before you start: a leg
already waiting in a queue cannot be redirected into new SWML. So you design
the release, not the redirect.

## How it works

Everything after `enter_queue` in the document is the release path. A caller
who reached an agent never gets there; a caller whose wait ran out does.

```python
service.add_verb("enter_queue", {
    "queue_name": QUEUE,
    "transfer_after_bridge": "false",
    "wait_time": MAX_WAIT,
    "wait_url": f"{PUBLIC_URL}/hold-music",
    "status_url": f"{PUBLIC_URL}/queue-status",
})
service.add_verb("play", {"url": "say:Nobody is free yet. We will call you back..."})
service.add_verb("hangup", {})
```

`wait_time` is what makes the release reachable at all. Without a cap the call
waits until the caller gives up, and the verbs below never run.

`transfer_after_bridge` is a string, not a boolean. It holds a URL or inline
SWML, and `"false"` is how you say "carry on in this document instead". Passing
a real boolean fails schema validation.

Remembering why somebody called and owing them a call back are two different things.
`remember(number, reason)` runs at intake, before the queue. `owe_callback(number)`
runs only once the wait has actually run out. A caller who reached an agent is
remembered and never rung, which is the bug that shape exists to avoid. A promise with
no number is refused, because a promise you cannot ring is not a promise.

When the callback goes out, the context travels **in the document** handed to
`dial`, not in a lookup the caller waits through. The returning call says what it is
about, then rejoins them to the same queue.

The promise is discharged only after the dial request has gone out. Discharging first
would drop a caller silently whenever a dial failed, which is the one outcome this
recipe exists to avoid.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env
python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/queue`. Call
`remember(number, reason)` from your intake, `owe_callback(number)` when a caller's
wait runs out, and `call_back(number)` when an agent frees up.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

Both documents validate against the SWML schema. The verifier asserts:

- the verbs are `answer`, `enter_queue`, `play`, `hangup`, so the release path
  sits after the queue
- `wait_time` is a positive cap, and `transfer_after_bridge` is the string
- what the caller hears is a promise to ring back, not a request to keep holding
- `/hold-music` returns valid SWML, so `wait_url` points at something
- `remember()` records a reason without owing anything, and `owe_callback()`
  refuses an empty or missing number
- the callback is a documented `dial` carrying an inline document
- that document names the reason the caller gave, and reconnects to the same
  queue
- the promise is discharged after the dial, and a second `call_back` rings
  nobody
- a caller who was never owed anything is never dialled
- a caller with no recorded context still gets a sensible call, and a dial that
  raises keeps the promise

## Limitations

The promises live in a dict here. A restart loses them, which means callers
who were promised a call do not get one. Anything real writes them where a
restart cannot reach.

Nothing here detects the release. The document falls through to the release path, but
learning that happened server-side needs the queue status payload, which no
specification we hold describes. `owe_callback` is therefore called by whatever
watches the queue, and that watcher is the part this recipe does not show.

## What to change first

Remove `wait_time`. The caller waits in the queue indefinitely, the release
path below is unreachable, and the promise is never made.
