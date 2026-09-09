# Barge into a live call

> A visitor with full audio, whose leaving does not end the call.

**Scenario:** a supervisor stepping into a support call to speak to everyone

## What this demonstrates

A third party joins a call in progress and everyone hears them. It is the loud
counterpart to whispering: no target, no mute, and a beep so the customer knows
somebody arrived.

The part worth getting right is the exit. A visitor who hangs up must leave the
call running.

## How it works

The same `join_conference` that coaches, with the coaching turned off.

```python
FunctionResult("Joining.").join_conference(
    name=room,
    muted=False,        # heard by everyone
    coach=None,         # aimed at nobody in particular
    end_on_exit=False,  # a visitor, not the host
    start_on_enter=False,
    beep="onEnter",
)
```

Two fields decide what kind of arrival this is. `coach` aims audio at one leg;
without it, speech goes to the room. `muted` keeps you out of the mix; without
it, you are in it. Barging is both of those off, and whispering
(`whisper-to-an-agent-mid-call`) is both on.

`end_on_exit` is the field that protects the call. Left at its default of
false, the supervisor can drop off and the agent and customer keep talking. Set
it true and every barge-in ends with the customer hung up on. The SDK helper
omits fields already at their default, so `end_on_exit` does not appear in the
emitted document at all.

`beep: "onEnter"` is a deliberate choice rather than a leftover. Somebody new
can now hear the customer, and the customer should get some signal of it.

Two checks run before anything is emitted, and the order matters. The caller's
number has to be on the supervisor list, then the room has to be on the floor
list. Both are sets in code, because barging is audible to a customer and
neither is something the model gets to widen.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a supervisor-only number's SWML webhook at
`https://<user>:<password>@<your-host>/barge/`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and runs the handler, asserting:

- nothing in the document joins a conference; only the handler does
- the join is unmuted and carries no `coach` key
- `end_on_exit` is absent, which is its default of false
- `start_on_enter` is false, so arriving starts nothing
- `beep` is `onEnter`
- every allowed floor resolves, and three disallowed rooms are refused
- two callers who are not supervisors are refused before the room is looked at

## Limitations

The caller check is caller ID, and caller ID can be spoofed. It is a floor, not
a door: `require-verification-before-unlocking-tools` is the same shape with a
PIN behind it.

There is no notice to the agent that a supervisor arrived, other than the beep
the customer also hears.

## What to change first

Set `end_on_exit=True` and barge into a call, then hang up. The customer is
disconnected, which is the failure this field exists to prevent.
