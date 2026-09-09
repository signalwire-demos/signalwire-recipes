# Detect an answering machine

> Find out who picked up before you say anything, and leave the message after
> the beep.

**Scenario:** a bike shop telling customers their repair is ready

## What this demonstrates

An outbound call that classifies whoever answered before it speaks. A person and a
voicemail both hear the repair message, voicemail playback waits until after the beep,
and a fax tone gets hung up on.

The classification happens in the document, so no code of yours is in the loop
while the call is deciding.

## How it works

`detect_machine` runs first and blocks until it has an answer. The outcome
lands in the `detect_result` variable, and is also POSTed to `status_url` if
you want it for reporting.

```yaml
- detect_machine:
    detectors: "amd,fax"
    detect_message_end: true
    initial_timeout: 4.5
    end_silence_timeout: 1.0
- switch:
    variable: detect_result
    case:
      human:   [...]
      machine: [...]
      fax:     [{ hangup: {} }]
```

`detect_message_end` is the field that makes voicemail work. With it on, detection
holds until the greeting finishes, so the message is played after the beep. With it
off, the call talks over the outgoing greeting and the recording catches half a
sentence.

The documented values are lowercase: `machine`, `human`, `fax`, `unknown`, `detecting`
and `error`. The last three go to `default`, which plays the message and nothing else.
That is the safe thing to say when the classifier could not decide, because it works
read to a person or recorded by a machine.

The document travels with the origination on `dial`, so the classification runs
on the leg being answered. There is no separate call to bridge first.

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

With the HTTP layer replaced by a recorder, the verifier asserts:

- one documented `dial`, carrying the document inline
- `detect_machine` precedes the `switch`, and nothing plays before it
- `detect_message_end` is on, with both timeouts set
- the switch reads `detect_result`
- every case is one of the six documented values, and `human`, `machine` and
  `fax` are all handled
- a fax hangs up, a human and a machine both hear the message
- no branch offers a keypress, because the document collects no digits
- the three unclassified outcomes fall to the default rather than being cased

## Limitations

Detection costs time. `initial_timeout` is how long the call waits for a voice
before giving up, so a human hears a pause before you speak. Shortening it
trades accuracy for that pause.

AMD is a guess. A slow talker is classified as a machine, and a short voicemail
greeting as a human. That happens often enough that the message has to make sense
either way.

## What to change first

Set `detect_message_end` to false and call your own voicemail. The message
starts during the greeting, and the recording gets the tail of it.

Swap the `play` in the machine branch for a `send_sms` verb carrying a link, and the same document is missed call text-back. On this outbound call the customer is the `to` of the dial, so `to_number` is that number, not `call.from`, which is your own line here. `from_number` is a messaging-enabled number you own. `text-the-caller-during-the-call` shows the verb on an inbound call.
