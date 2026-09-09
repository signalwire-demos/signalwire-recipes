# Listen to a live call

> A copy of the audio arrives at your socket while the call carries on.

**Scenario:** a supervisor console that monitors a support line

## What this demonstrates

Call audio forked to a WebSocket you own, in real time, with nothing added to
the call. Nobody is conferenced in and nothing is announced, because a tap
copies media rather than joining the room.

This is how you build a monitoring console. Speaking to the people on the call
is a different mechanism entirely, and it is a conference.

## How it works

`tap` takes a `uri`, and that is its only required field. The scheme decides the
transport: `ws://`, `wss://` or `rtp://`.

```yaml
- tap:
    uri: "wss://your-host.example.com/ws/audio"
    direction: both
    codec: PCMU
    control_id: supervisor-audio
```

`tap` comes before `connect`. `connect` owns the bridge until the far leg ends,
so a tap placed after it does not start until the conversation is over. That
ordering is the same trap `record_call` and `live_transcribe` have.

`direction` decides whose audio you receive. `listen` is what the party hears,
`speak` is what they say, and `both` is the conversation. A console that only
gets `speak` records half a call and sounds broken.

`codec` is `PCMU` or `PCMA`. Whatever is on the other end of the socket has to
decode it, and PCMU is the default for a reason.

`control_id` is the handle `stop_tap` needs. Without one the tap runs for the
life of the call and there is no way to end it early.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set AUDIO_WS
python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/listen`. The socket
at `AUDIO_WS` has to be accepting connections before the call arrives.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

The document validates against the SWML schema. The verifier asserts:

- the verbs are `answer`, `tap`, `connect`, `hangup`, in that order
- `tap` precedes `connect`, so the bridged leg is inside the tap
- the URI is one of the documented schemes, and a WebSocket one here
- `direction` is `both` and the codec is documented
- a `control_id` is set, so the tap can be stopped
- no `play`, `prompt`, `join_conference` or `say` appears anywhere. That is
  what "the participants hear nothing" means in an artifact
- the status webhook records the tap's state under its control id

## Limitations

You have to run the socket. A tap with nowhere to connect is a call that works and a console that is silent. The
failure is on your side of the wire.

The audio is raw PCMU frames, not a file and not a transcript. Turning it into
words is `start-live-transcription`, which is a different verb and does not
need a socket at all.

## What to change first

Move `tap` below `connect` and call the number. The console stays silent for
the whole conversation, and the tap starts as the call ends.
