# Send a fax

> A fax is sent from a document URL and its status webhook reports pages and result.

**Scenario:** a clinic sending a referral PDF to another office

## What this demonstrates

Fax is one REST call, `POST .../Faxes` with `To`, `From` and a `MediaUrl`
pointing at a PDF, followed by a wait. Transmission takes minutes and can fail
half-way, so the outcome (`delivered` with `NumPages`, or `failed` with an
`ErrorCode`) arrives at `StatusCallback`; the create response only says
`queued`.

## How it works

```python
client.compat.faxes.create(To=to, From=FROM, MediaUrl=pdf_url, Quality="fine",
                           StatusCallback=f"{PUBLIC_URL}/fax-status")
```

The send goes through the Compatibility API's Faxes endpoint
(`/api/laml/2010-04-01/Accounts/<project>/Faxes`). There is no native
`/api/fax` send; the native surface has fax *logs* (`GET /api/fax/logs`) for
reconciliation. From inside a call the same operation is the SWML verb
`send_fax`; over RELAY it is `call.send_fax`. Non-final statuses (`queued`,
`processing`, `sending`) are ignored by the handler; final ones are recorded.

## Run it

```bash
cd python
pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... SIGNALWIRE_FAX_NUMBER=+1555... PUBLIC_URL=https://<your-host>
python app.py
python -c "import app; print(app.send('+1555...', 'https://<public-url>/document.pdf'))"
```

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, `send()` must make one documented POST with the required
`To`, `From`, `MediaUrl` and a `StatusCallback`, checked against
`tools/openapi/compat.json`. The status webhook must record only final statuses, with
page count or error code.

## What to change first

Point `MediaUrl` at a document your own app generated a minute earlier, and
retry on `busy` or `no-answer` with a backoff, because the fax world still has both.
