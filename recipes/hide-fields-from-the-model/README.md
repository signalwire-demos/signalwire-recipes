# Show the AI model only the fields it needs

> Load the whole record, expose a curated slice, and keep the rest out of the prompt entirely.

## What this demonstrates

The agent answers questions about a customer while never receiving that customer's
risk score, internal notes, or margin. Those fields are dropped server-side before
anything reaches the prompt.

This is stronger than instructing the model to stay quiet about them. A field the
model never received cannot be leaked, summarised, inferred aloud, or extracted by
a caller who asks cleverly.

## How it works

`get_account` is a SWAIG tool with no parameters. The handler loads the full
record from your own system, builds an explicit allowlist projection
(`EXPOSED = ("first_name", "plan", "renewal_date", "open_tickets")`) and returns
it as the tool's response text, `FunctionResult(json.dumps(projection))`. That
response is the only thing the model receives; `risk_score`, `margin_pct`,
`internal_notes` and `card_last_four` are never in the conversation.

The prompt never names the hidden fields either. A prompt that says "do not
mention the risk score" tells the model a risk score exists.

## Run it

```bash
cd python
pip install -r requirements.txt
python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/account/`, using the credentials from your `.env`.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It runs the tool handler as the platform would, and asserts the response contains
every exposed field and none of the hidden ones. It then renders the SWML and asserts
the prompt does not mention a hidden field.

## Limitations

Anything you put in the projection is in the prompt, permanently, for that call. Add
fields deliberately - a projection that grows to match the record defeats the point.

## What to change first

Add a field to the record but not to the projection, then try to get the agent to
reveal it.
