# Take a voicemail

> When the bridge to the owner does not happen, `connect`'s failed branch plays a prompt and `record` takes the message in the foreground. Recording events, with the download URL, go to `status_url`.

**Scenario:** a one-person shop whose number should take a message when the owner cannot pick up

## What this demonstrates

`connect` dials the owner with a `timeout`. Per the
[connect reference](https://signalwire.com/docs/swml/reference/connect),
`result` runs "once the peer leg of the call has ended" against
`connect_result`, which is `connected` or `failed`. You put the voicemail in the
`failed` case: a prompt, then `record`. The
[record reference](https://signalwire.com/docs/swml/reference/record)
describes `record` as recording "in the foreground pausing further SWML
execution until recording ends". It stops on a terminator digit, on silence,
or at `max_length`. The platform sets `record_url` and `record_result` on the
call and POSTs recording events to `status_url`.

## How it works

```yaml
- connect:
    to: "+15550100001"
    timeout: 20
    result:
      case:
        connected:
          - hangup: {}
        failed:
          - play: { url: "say:Leave a message after the tone." }
          - record:
              beep: true
              format: "mp3"
              max_length: 120
              end_silence_timeout: 5
              terminators: "#"
              status_url: "https://your-host.example.com/recording-status"
          - play: { url: "say:Thanks. We will call you back." }
          - hangup: {}
```

Per the reference, `beep` plays a tone before recording and `terminators` is
the digit string that stops it. `end_silence_timeout` is the silence that ends
it, and `max_length` is the ceiling in seconds. The `status_url` callback
carries the recording state, the download URL, the duration and the recording
id. You receive it at an endpoint you run; this recipe does not serve one.

The `connected` branch runs after the owner hangs up and only ends the call.
The Python surface builds the same document with `SWMLService`, reading the
owner's number and your host from the environment.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set OWNER_NUMBER, PUBLIC_URL and the basic-auth pair
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/voicemail/`, call, and let it ring out.
`PUBLIC_URL` is where you receive the recording callback; a request bin is
enough to see the payload.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

It validates both surfaces against the bundled schema and asserts the following.

- the main section is `answer` then `connect`, to the owner's number with a 20 second timeout
- `result.case` has exactly `connected` and `failed`; `connected` only hangs up
- `failed` is `play`, `record`, `play`, `hangup`, with the exact prompt and the exact thanks
- the `record` equals the expected object: beep, mp3, 120 seconds, 5 seconds of silence, `#`, and a `status_url` on your host
- the Python and YAML surfaces render the same document

## Limitations

The verifier proves the document. The recording, its URL and the callback are
what the platform does on a live call; `record_result` says `success` or
`failed` there.

`initial_timeout` is the "time in seconds to wait for the start of speech",
default four, per the bundled schema. A caller who stays silent that long
records nothing, and the thanks still plays.

## What to change first

Change `terminators` to `"*"` and `max_length` to `30` in both surfaces and run
the verifier. The `record` equality fails. The `record` object in each surface
defines every setting of the message, and the verifier holds both to one value.

Swap the `record` in the failed branch for a `send_sms` verb carrying a link, and the same document is missed call text-back. The caller who reached no one gets a text instead of a tone. `text-the-caller-during-the-call` shows the verb.
