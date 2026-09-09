# Transcribe a voicemail and text it to the owner

> `<Record transcribe="true" transcribeCallback="...">` makes the platform transcribe the message and POST the words to your URL. One compat message then sends the owner the transcription and the recording link.

**Scenario:** a one-person shop reads its voicemail as a text instead of dialling in for it

## What this demonstrates

Voicemail is only useful if someone listens to it. Turning on transcription
is one attribute on the `Record` verb. The platform does the rest: it POSTs
the words to the URL you name, and your handler forwards them. The callback's
own reference names that use, "forwarding the body via SignalWire SMS", which
is what this does.

The trap is in the payload. It carries `TranscriptionSid`, `TranscriptionText`,
`TranscriptionStatus`, `TranscriptionUrl`, `RecordingSid` and `RecordingUrl`,
and nothing about the call. There is no `From`. Your app builds the document
per call, so the caller's number goes into the callback URL. The signature
check covers that URL, query string and all.

## How it works

```python
def callback_url(caller):
    return f"{PUBLIC_URL}/transcription?from={quote(caller or 'unknown', safe='')}"

def voicemail_document(caller):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f"  <Say>{escape(GREETING)}</Say>\n"
            f'  <Record transcribe="true" '
            f"transcribeCallback={quoteattr(callback_url(caller))} "
            f'maxLength="{MAX_SECONDS}" playBeep="true" finishOnKey="#" timeout="5"/>\n'
            "</Response>\n")
```

The [Record reference](https://signalwire.com/docs/compatibility-api/cxml/reference/voice/record.md)
documents every attribute used here. `transcribe` is "Identifies whether to
produce a text transcription of the recording", default false.
`transcribeCallback` is "A URL to which SignalWire will make a `POST` request
to once the transcription is complete". `timeout` is "The number of seconds of
silence that ends a recording", and `finishOnKey` is the digit set that ends
it early.

`TranscriptionStatus` is `completed` or `failed`. A failed transcription still
gets a text, with the recording link and no words. A voicemail nobody knows
about is worse than one nobody can read.

Two guards, because the handler spends money. The route refuses a callback
SignalWire did not sign, using the check from `verify-a-webhook-signature`
over the full URL including the query. And each `TranscriptionSid` is texted
once, because the callback's reference calls these "advisory, best-effort
notifications" whose "delivery can be delayed".

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # credentials, signing key, PUBLIC_URL, OWNER_NUMBER
python app.py                    # serves POST /voice and POST /transcription
```

The TypeScript surface is the same two routes on `node:http`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point a number's voice handler at `PUBLIC_URL/voice`, call it, leave a message
and hang up. The text arrives when the transcription does.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives both routes and records the outgoing message. It asserts
the following.

- the voice route answers `text/xml` that parses: `Response` holding a `Say` and a `Record` with `transcribe="true"`, `maxLength="120"`, `playBeep`, `finishOnKey` and `timeout`
- the `transcribeCallback` is this app's transcription route carrying the caller as a query parameter
- a signed `completed` callback sends one documented compat message to the owner, whose body is the caller, the words and the recording link
- the same callback again sends nothing and answers "already texted"
- a send whose response never arrives keeps its claim, so the same transcription afterwards sends nothing
- a signed `failed` callback sends a message naming the recording and saying it was not transcribed
- an unsigned callback is 403 and no message is sent
- the compat spec's payload requires exactly the six fields used here, carries no caller field, and its status enum is `completed` or `failed`
- the callback's own description names `transcribe=true` and calls the callbacks best-effort
- the TypeScript surface renders the same document and sends the same two messages
- a failed send on the TypeScript surface answers 500 rather than ending the process, and the request after it is served and finds the claim

## Limitations

The verifier proves the document, the callback handling and the message. The
quality of a transcription, and how long it takes to arrive, are live
questions.

The claim on a transcription is taken before the text is sent and is never
given back. A send that reached SignalWire and lost its response looks like one
that never arrived, so a lost send is not retried. The marker directory stands
in for a unique key in your table.

SWML's `record` and `record_call` carry no transcription parameter in 3.0.1,
so this is a cXML recipe. `take-a-voicemail` is the SWML version of the
recording itself.

`Record` also takes an `action` URL, which is the recording-completed hook and
a different callback from this one. Use it when you need to say something to
the caller after the beep stops.

The transcription text is customer speech. It is sent onward as a text message
here, so the number in `OWNER_NUMBER` is the only place it lands.

## What to change first

Drop `?from=` from `callback_url` and run the verifier. The document assertion
fails, and on a real call the owner would get a text saying "Voicemail from
unknown", because the payload never carried the caller.
