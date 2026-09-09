# Extract structured data after a call

> The call ends and a typed record arrives at your webhook.

**Scenario:** a support line for a bicycle retailer

## What this demonstrates

Every call leaves behind a row someone wants: what the caller needed, how it ended,
whether to ring them back. The post-prompt runs once after the conversation and
returns that as JSON to your webhook. Nobody has to listen to a recording to write the
record.

The model writes the JSON. That is the part to design around, and this recipe
validates before it stores.

## How it works

`set_post_prompt()` puts a second prompt in the document. The platform runs it
after the call ends, then POSTs the result to `post_prompt_url`, which the SDK
fills in for you.

```python
self.set_post_prompt(
    'Return only JSON, no prose, with exactly these keys: '
    '"outcome" (one of resolved, escalated, callback_requested, abandoned), '
    '"reason" (one short sentence), '
    '"callback_number" (E.164, or null if none was given).'
)
```

Name the keys and the allowed values. A post-prompt asking for "a summary of the
call" returns a paragraph, and a paragraph is not a row.

`on_summary(summary, raw_data)` receives it. The SDK looks for the payload in
`summary`, then in `post_prompt_data.parsed[0]`, then by parsing
`post_prompt_data.raw`, so the handler sees a dict either way.

Then the handler checks it. A model occasionally produces an `outcome` outside the four allowed values, or a
`callback_requested` with no number. It also produces a bare `+` where E.164 was asked
for, and keys nobody requested. None should
reach your database. A failed record goes to a quarantine list with the reason,
because the call still happened and losing it is worse than flagging it.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/support/`, using the credentials you set. Without them the request is refused.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and asserts:

- the post-prompt names all three keys, and a `post_prompt_url` is set
- a well-formed summary is filed against its `call_id`
- ten malformed summaries are quarantined, each with the reason it failed
- nothing malformed reaches the filed records
- both delivery shapes, `parsed` and a raw JSON string, resolve to the same dict

## Limitations

The post-prompt is a second model call, so it costs a turn and can fail. Treat a
missing summary as normal and reconcile against call logs rather than assuming
one record per call.

It runs after the conversation. Anything you need *during* the call belongs in a
tool, where your code answers instead of the model summarising.

## What to change first

Add a `sentiment` key to the post-prompt and leave the validator alone. Every summary
is now quarantined as `unexpected sentiment`, because the schema is closed at both
ends. Widening it is a code change, which is the point.
