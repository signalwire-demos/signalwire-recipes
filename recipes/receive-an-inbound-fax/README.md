# Receive an inbound fax

> An inbound fax on a number is received to a URL and your webhook is told when it lands.

**Scenario:** an intake line that turns faxed forms into files your system can process

## What this demonstrates

Receiving a fax is a three-verb SWML document on a fax-capable number:
`answer`, `receive_fax`, `hangup`. The platform handles the tones and the page
transfer; when the fax completes it POSTs the result to `status_url`: success, page count and
the document URL. Nothing about T.30 reaches your code.

## How it works

```yaml
- answer: {}
- receive_fax: { status_url: "https://<your-host>/fax-received" }
- hangup: {}
```

The Flask route at `/fax-received` stores the document URL and page count when
`success` is true and ignores a failed receive. From there the document is a
normal file: OCR it, extract fields with a model, file it. The Telnyx
"fax-to-structured-data" stems are this recipe plus a parser.

Fax media URLs can be protected so they require API auth to fetch (Dashboard → Media
URL protection). The Compatibility API offers the same receive as `<Receive
action=...>`, and inbound fax history is in `GET /api/fax/logs`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script, set `status_url`, and
assign it to a fax-capable number.

Python:

```bash
cd python
pip install -r requirements.txt
PUBLIC_URL=https://<your-host> python app.py
```

Point the number's SWML webhook at `https://<your-host>/fax`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SWML schema and consist of exactly
`answer → receive_fax(status_url) → hangup`; the status webhook stores pages
and the document URL only for a successful receive.

## What to change first

Feed the document URL to `extract-structured-data-after-a-call`'s sibling
pattern, a model with a typed schema, and post the JSON to your system.
