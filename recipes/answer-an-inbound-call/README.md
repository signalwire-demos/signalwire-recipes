# Answer an inbound call

> Accept an incoming call, greet the caller, and hang up cleanly.

**Scenario:** an out-of-hours greeting for a bicycle shop

## What this demonstrates

The smallest complete call. A number rings, SignalWire fetches a document from
your URL, and the document answers the call, speaks a line and hangs up. Three
verbs, no account state, no AI.

A queue, an agent or a transfer is this document with more verbs in it.

## How it works

SignalWire fetches the document when the call arrives and runs `sections.main`
in order.

```yaml
sections:
  main:
    - answer:
        max_duration: 300
    - play:
        url: "say:Thanks for calling Ridgeline Cycles. We are open until six."
    - hangup: {}
```

`answer` decides when the call is picked up. It is not a prerequisite for audio:
`play` carries `auto_answer`, true by default, so a document that opens with `play`
answers the call on its way to speaking. Answering explicitly is worth the line
because it puts the moment under your control.

`play` speaks its `url` when the value starts with `say:`. Any other URL is a file to fetch and play instead. That is how you swap a synthesised
voice for a recorded one, without touching the rest.

`hangup` ends the call. Leave it out and the call stays open, silent, until
`max_duration` expires. That is why `max_duration` is set at all. It is a backstop
against a call nobody ended, not a feature of this greeting.

The Python surface builds the same three verbs through `SWMLService`. The greeting
comes from the environment, and the document is validated against the SWML schema
before it is served.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env
python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/greeting`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SDK's bundled SWML schema. The verifier
asserts:

- the verbs are exactly `answer`, `play`, `hangup`, in that order
- `answer` precedes `play`, so the call is answered explicitly
- `max_duration` is set to a positive integer
- the played URL is a `say:` string with something after the colon
- a POST to the route, which is how SignalWire fetches it, returns the document

## Limitations

The bundled schema requires `play` to be an object with a `url`. The shorter
`play: "say:..."` form appears in the docs and will not pass local validation,
so prefer the object form in anything you lint.

There is no input here. Collecting a digit or a phrase is `build-an-ivr-menu`
and `collect-speech-input-and-branch`.

## What to change first

Set `auto_answer: false` on the `play` and remove the `answer` above it. The greeting now plays as early media, before the call is answered. That is how you
say something to a caller you are not yet billing for.
