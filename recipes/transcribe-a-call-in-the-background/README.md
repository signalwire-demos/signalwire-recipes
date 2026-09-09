# Transcribe a call in the background

> `calling.transcribe` starts transcribing a live call in the background by `control_id`, and `calling.transcribe.stop` ends it. SignalWire may then send the documented transcript callback to your `status_url`, whose `params.text` holds the text when there is any.

**Scenario:** you want each support call's text filed against its ticket

## What this demonstrates

The vendored REST spec has a `calling.transcribe` variant of the call command.
Its params require `control_id` and take a `status_url`, "An HTTP or HTTPS URL
that receives the status callback when the transcription completes".
`calling.transcribe.stop` takes the same `control_id`. The spec also documents
what may arrive: the transcribe status callback, whose `event_type` is
`calling.transcript.completed` or `calling.transcript.failed`. Its
`params.text` is "The transcribed text of the call. Omitted when there is no
transcribed text." The spec calls the callback advisory and best-effort. You
reach the two commands as `client.calling.transcribe` and
`client.calling.transcribe_stop`.

## How it works

```python
def start(call_id):
    return client.calling.transcribe(call_id, control_id=CONTROL_ID, status_url=STATUS_URL)

def record(event):
    params = event["params"]
    TRANSCRIPTS[params["call_id"]] = {
        "status": event["event_type"].rsplit(".", 1)[-1],   # completed | failed
        "text": params.get("text"),
        "at": event["timestamp"],
    }
```

What the platform receives, then what it sends you:

```http
POST /api/calling/calls
{"command": "calling.transcribe", "id": "<call_id>",
 "params": {"control_id": "call-transcript", "status_url": "https://<your-host>/transcripts"}}

POST https://<your-host>/transcripts
{"event_type": "calling.transcript.completed", "timestamp": 1788350400.5,
 "project_id": "...", "space_id": "...",
 "params": {"id": "...", "call_id": "<call_id>", "segment_id": "...", "text": "Hi, this is ..."}}
```

`record` reads `text` with `.get`, because the spec omits it when nothing was
transcribed, whichever status the event carries; the verifier's failed fixture
omits it. Before `record` runs, the route checks SignalWire's signature over
the request, `hex(HMAC(signing_key, url + raw_body))`, as
`signalwire.com/docs/swml/guides/webhook-security` documents it and
`verify-a-webhook-signature` explains, so a forged callback cannot overwrite a
transcript. `GET /transcripts/<call_id>` serves what arrived, or `pending`
until something does, to a caller with your `READ_TOKEN` as a bearer token.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, TRANSCRIBE_STATUS_URL, the signing key, READ_TOKEN
python app.py                    # the status URL, on port 8080
```

```bash
cd python                        # in another shell, during a live call
python app.py start <call_id>
python app.py stop <call_id>     # later, with the same control id
```

The status URL needs a public HTTPS address. For a local run, expose port 8080
with a tunnel such as ngrok, and set `TRANSCRIBE_STATUS_URL` to
`https://<your-host>/transcripts`. The call id is the `id` of a call in
progress; `handle-call-status-callbacks` or the calling logs give you one. When
the call ends, read the transcript with your token. Paste the `READ_TOKEN` value
from `.env`; `load_dotenv()` loads it into the app, not into your shell:

```bash
curl -H "Authorization: Bearer YOUR_READ_TOKEN" "https://YOUR_HOST/transcripts/CALL_ID"
```

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier swaps the SDK's HTTP layer for a recorder and drives the Flask app
with its test client. It asserts the following.

- `start` and `stop` each make one `POST` to the documented calling path, and each body equals one expected object
- the spec's two variants require exactly `control_id`, and every param sent is documented
- the spec's callback has exactly two event types, and it says `text` is omitted when there is no transcribed text
- two fixture callbacks, one completed with text and one failed without it, carry every required field at both levels and nothing undocumented
- the route refuses an unsigned callback, and one signed with another key, with 403, and the store stays empty
- a callback signed with the SHA-256 header is accepted; a valid SHA-1 signature beside an empty SHA-256 header is refused, because the header that is present decides
- a read without the bearer token is refused with 401
- an unknown call reads as pending; after the signed callbacks, the completed call reads back its text and the failed one reads back no text
- a status URL configured with its own query string is signed as that URL, once; a signature over the query appended twice is refused

## Limitations

You prove the requests and the handler against the documented shapes. What the
platform transcribes, and when the callback arrives, are the platform's side of
a live call. The spec calls the callback best-effort, so a transcript that
never arrives is a case your job has to expect.

SWML has a `transcribe` verb for the same job at document time, but it is
absent from the 3.0.1 bundled schema. This recipe cannot prove it offline, so
it uses the REST command instead.

## What to change first

Change `record` to read `params["text"]` and run the verifier. The failed
callback raises `KeyError`, because the spec omits the field, which is why the
handler reads it with `.get`.
