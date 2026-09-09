# Move a TwiML app by changing the endpoint

> A TwiML app moves to SignalWire by changing the REST base and the credentials. The compat client posts the same Calls body to the LaML path on your Space, and your cXML handler serves the same document it served before.

**Scenario:** a shop's Twilio voice app, a `<Say>` and a `<Hangup/>` behind one URL, moving without a rewrite

## What this demonstrates

The compatibility API page, https://signalwire.com/docs/compatibility-api,
says to "update the base URL from api.twilio.com to your-space.signalwire.com".
It adds that this "is not required if using the SignalWire Compatibility SDK".
It also says "Your existing TwiML/cXML response handlers work without
modification". The SDK's compat namespace builds every path as
`/api/laml/2010-04-01/Accounts/<project id>/...` on your Space. The project id
sits where Twilio had the account SID, and the API token is the password; the
SDK sets that basic-auth pair in `rest/_base.py:38` (`self._session.auth = (project, token)`). The verifier proves the
path and the body, not the credentials, which the recorder never sees. The
compat spec's Calls create requires `To` and `From` and takes `Url`, "The URL to
handle the call". The handler is a Flask route that returns the TwiML document
as `text/xml`, and the document is the one you had.

## How it works

```python
CXML = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        "  <Say voice=\"Polly.Salli\">{greeting}</Say>\n"
        "  <Hangup/>\n"
        "</Response>\n")

def place(to):
    return client.compat.calls.create(To=to, From=FROM, Url=VOICE_URL)

@app.post("/voice")
def voice():
    return Response(CXML.format(greeting=GREETING), mimetype="text/xml")
```

What the platform receives, then what it fetches from you:

```http
POST /api/laml/2010-04-01/Accounts/<project id>/Calls
{"To": "+1555YYYYYYY", "From": "+1555XXXXXXX", "Url": "https://<your-host>/voice"}

POST https://<your-host>/voice
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Salli">Thanks for calling Ridgeline Cycles. The workshop opens at nine.</Say>
  <Hangup/>
</Response>
```

`RestClient()` reads the Space, project id and token from the environment; the
compat client is `client.compat`. That is the whole of the change on the REST
side. The handler did not change at all.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, CALL_FROM, VOICE_URL
python app.py                    # the handler, on port 8080
```

```bash
cd python                        # in another shell
python app.py +1YYYYYYYYYY       # place a call to hear the greeting
```

The handler needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and set `VOICE_URL` to `https://<your-host>/voice`. A
Twilio-shaped client in another language does the same thing by pointing its
base URL at `https://<your-space>.signalwire.com/api/laml/2010-04-01`.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier swaps the SDK's HTTP layer for a recorder and drives the Flask
handler with its test client. It asserts the following.

- `place` makes one `POST` to `/api/laml/2010-04-01/Accounts/<project id>/Calls`, the path the compat namespace builds from the project id
- the body is exactly `To`, `From` and `Url`, the request is documented, and the compat spec requires exactly `To` and `From`
- a `POST` to `/voice` answers `200` as `text/xml`
- the document parses, its root is `Response`, and its children are `Say`, with the exact greeting and the `Polly.Salli` voice, then `Hangup`
- the project id and the API token appear nowhere in the document

## Limitations

You prove the request and the document. Which TwiML verbs and attributes the
platform runs is defined by the public cXML reference. `<VirtualAgent>` is
deprecated, `<Play>` inside `<Gather>` has no `digits`, and `<Start>`,
`<Siprec>`, `<Autopilot>`, `<Client>` and `<Task>` have no reference pages.
Check your handlers' verbs against the reference before you move.

The document here is static. A handler that reads request parameters keeps
reading the same names; the compat spec documents them under the Calls
webhooks.

## What to change first

Change `CXML` to answer with `<Response><Say>Hello</Say></Response>` and run
the verifier. The children assertion fails on the missing `Hangup`, and the
greeting assertion on the text. The verifier pins the document, because the
document is the part you brought with you.
