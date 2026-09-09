# Build a conference call

> A room is a name. Two calls that say it are in the same conference.

**Scenario:** a standup for a distributed team

## What this demonstrates

Several callers in one audio room, with nothing created beforehand. `join_conference`
takes a name, and every call using that name is in that conference. Once the room
exists, members can be muted, removed and listed over REST.

The interesting part is not joining. It is who is allowed to end the room.

## How it works

`name` is the only required field, and it is the whole identity of the room.

```yaml
- join_conference:
    name: standup
    start_on_enter: false
    end_on_exit: false
    beep: onEnter
    max_participants: 25
```

`start_on_enter` and `end_on_exit` are per participant, which is what lets one
document be a host and another a guest. The host starts the room and closes it;
a guest joining early waits, and a guest hanging up leaves everyone else
talking. Give every participant `end_on_exit: true` and the first person to
drop off ends the meeting.

Two fields are narrower than they look. `beep` is one of `true`, `false`,
`onEnter` or `onExit`, and `status_callback_event` takes a **single** event
name from `start`, `end`, `join`, `leave`, `mute`, `hold`, `modify`, `speaker`
or `announcement`. A space-separated list of events is a natural thing to write
and does not validate.

Membership control is Compatibility REST, once the room has a SID:

```python
client.compat.conferences.update_participant(conf, call, Muted="true")
client.compat.conferences.remove_participant(conf, call)
client.compat.conferences.list_participants(conf)
```

Removing a participant ends their call and leaves the room running.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env
python app.py
```

Point one number at `https://<your-host>/conference/host` and the others at
`https://<your-host>/conference`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

All three documents validate against the SWML schema. The verifier asserts:

- the host, guest and hand-written documents all name the same room
- only the host has `start_on_enter` and `end_on_exit`
- `max_participants` is inside the documented range
- mute, unmute, remove and list are documented Compatibility requests,
  checked against `tools/openapi/compat.json`
- muting sends `Muted: true` and unmuting sends `Muted: false`
- both documents subscribe to `join`, and the webhook records the conference
  SID for a joining member

## Limitations

The room is a string, so anyone who can serve a document naming it can join.
There is no membership check here; if that matters, the name should be a secret
you mint per meeting rather than `standup`.

Participant control needs the conference SID, which arrives on the status
callback. Before the first participant joins there is nothing to address.

## What to change first

Set `end_on_exit: true` on the guest document. The first guest to hang up ends
the standup for everyone.
