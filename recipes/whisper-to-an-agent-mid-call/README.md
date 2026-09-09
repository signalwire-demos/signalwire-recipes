# Whisper to an agent mid-call

> The supervisor is heard by the agent and by nobody else.

**Scenario:** a support floor where a supervisor helps without taking over

## What this demonstrates

A supervisor joins a live call as a coach. The agent hears them, the customer
does not, and the call carries on. Nothing is transferred and nobody is put on
hold.

Coaching is aimed at a call, not at a room. That is the difference between
whispering to an agent and being a third person in the meeting.

## How it works

`join_conference` takes a `coach` field, and it holds the call ID of a
participant already in the conference.

```python
FunctionResult("Putting you through.").join_conference(
    name=ROOM,
    coach=call_id,      # the one leg that hears the supervisor
    muted=True,         # silent to everyone else
    beep="false",       # arriving without announcing it
    start_on_enter=False,
)
```

`muted` and `coach` are doing different jobs and both are needed. `muted` keeps
the supervisor out of the room's mix; `coach` mixes them into one leg anyway.
Set `muted` alone and the supervisor is silent to everyone including the agent.
Set neither and the customer hears a stranger.

`beep` is `"false"` because the default announces an arrival, which tells the
customer that something has changed.

`start_on_enter` is false so a supervisor arriving does not start anything, and
`end_on_exit` stays at its default of false so leaving does not end the
customer's call. The SDK helper omits fields already at their default, so
`end_on_exit` is absent from the emitted document rather than present and
false.

The handler checks two things before it emits anything, in that order. First
who is asking: the caller's number has to be on a supervisor list, because
reaching this console is not permission to listen to a customer. Then whether
the named agent is on a call, since joining with no `coach` target is a plain
participant the customer hears.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a supervisor-only number's SWML webhook at
`https://<user>:<password>@<your-host>/supervisor/`, and put the supervisors'
own numbers in `SUPERVISORS`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and runs the handler, asserting:

- nothing in the document joins a conference; only the handler does
- the emitted `join_conference` carries `coach` set to that agent's call id
- the supervisor is `muted` and joins with `beep: "false"`
- `start_on_enter` is false, and `end_on_exit` is absent, which is its default
- a second agent resolves to a different call id, so the mapping is real
- three ways of naming an agent who is not on a call are refused, and the
  refusal names who is available
- three callers who are not supervisors are refused before any lookup happens

## Limitations

`coach` needs a call ID, and this recipe keeps a hard-coded map of them. In
production those come from the conference status callbacks, which is
`build-a-conference-call`.

The caller check is caller ID, and caller ID can be spoofed. It is a floor, not
a door. `require-verification-before-unlocking-tools` is the same shape with a
PIN behind it.

Whispering is audible to the agent, so it interrupts them. There is no signal
to the agent that a supervisor has arrived beyond the supervisor speaking.

## What to change first

Delete `coach` and keep `muted: True`. The supervisor is now in the room and
audible to nobody. Delete `muted` too and the customer hears them.
