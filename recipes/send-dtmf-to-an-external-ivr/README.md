# Send DTMF to someone else's IVR

> The digits ride along with the origination, so they land while the tree is
> listening.

**Scenario:** reaching a carrier's porting desk without a person waiting on hold

## What this demonstrates

A call that dials someone else's phone tree and presses through it on its own.
The keys travel in the same request that places the call, and the platform
sends them once the far end answers.

There is an obvious way to send a digit that looks right and fires too late. The
mechanism below is the one that lands while a menu is listening.

## How it works

The obvious shape is `connect` to the tree and then `send_digits`. It does not
work. `connect` owns the bridge until the far leg ends, so the next verb runs
only once the IVR has hung up, and the digits go nowhere.

The `dial` command takes `send_digits` as a parameter instead. The spec
describes it as digits to send **after the call is answered**, which is the
moment a phone tree starts accepting input.

```python
client.calling.dial(**{
    "from": FROM,
    "to": IVR,
    "send_digits": ",,,,,,2,,,1",   # wait, press 2, wait, press 1
    "swml": after_answer,           # what our side does once through
})
```

The pacing characters are not the ones the `send_digits` verb uses. Here the
parameter allows `0-9`, `A-D`, `*`, `#`, `w` for a wait and `,` for a pause;
there is no capital `W`. A string written for the verb will not do here.

A menu that has not finished speaking has not started listening, so the pauses
are the design. Six pauses of greeting, press 2, three of submenu, press 1.

Writing that by hand gives `",,,,,,2,,,1"`, which is unreadable and un-tunable,
so the route stays as pairs and the string is built from it:

```python
ROUTE = [(6, "2"), (3, "1")]
```

A menu that got slower is a number you change rather than a run of commas you
count.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # add your credentials and IVR_NUMBER
python app.py
```

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer replaced by a recorder, `navigate()` must make one request.
The verifier asserts:

- the digits travel in the `dial` parameter, whose documented description says
  they are sent after the call is answered
- every character is one that parameter allows, and no capital `W` appears
- the string spells the route, pause for pause and key for key
- it begins with a pause, since a route that presses immediately is the bug
- the inline document is valid SWML and contains no `send_digits` verb, which
  after `connect` would fire once the bridge had already ended

## Limitations

This is open loop. Nothing checks that pressing 2 reached the menu you expected,
so a tree that changes its greeting sends your call somewhere else silently.
Closing the loop needs something listening to the far end, which is
`start-live-transcription` and a good deal more machinery.

Pauses are fixed when the call is placed. A queue that answers in four seconds
on Tuesday and forty on Monday cannot be paced by a constant.

## What to change first

Drop the leading pauses to one and place the call. The digit lands during the
greeting, the menu never registers it, and the call sits in the top-level tree.
