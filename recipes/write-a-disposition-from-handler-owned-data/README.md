# Write call dispositions from data your handlers recorded

> The qualification fields of a disposition come from what your tool handlers wrote to `global_data` during the call, not from the transcript or the model's summary.

**Scenario:** qualifying inbound leads for a fleet bicycle supplier

## What this demonstrates

Each tool handler validates one fact and writes it with a `set_global_data`
action. At the end of the call the platform POSTs to `post_prompt_url` with
`global_data` in the body. `on_summary` builds the record from that POST. The
call and caller identifiers come from the envelope and the qualification fields
from `global_data`. `on_summary` keeps the model's summary as a note that
nothing else reads, and leaves the transcript in the same POST unread.

The [post-prompt callback](https://signalwire.com/docs/apis/rest/webhooks/ai-post-prompt-callback)
documents the body. The platform includes `global_data` and `call_log` when
`action` is `post_conversation`, and `post_prompt_data` carries the model's
answer as `raw` and `parsed`.

## How it works

Handlers accept or refuse, and write only what they accepted:

```python
def record_budget(self, args, raw_data):
    amount = args.get("amount")
    if type(amount) is not int or amount <= 0:  # bool is an int in Python
        return FunctionResult("INVALID: ask for the budget as a number of dollars.")
    r = FunctionResult(f"Budget recorded: {amount} dollars.")
    r.add_action("set_global_data", {"budget": amount})
    return r
```

`on_summary` reads `global_data` from the POST body, not the summary:

```python
def on_summary(self, summary, raw_data=None):
    data = raw_data.get("global_data") or {}
    budget, can_sign = data.get("budget"), data.get("can_sign")
    return {"budget": budget, "can_sign": can_sign,
            "qualified": bool(budget and budget >= MIN_BUDGET and can_sign is True),
            "complete": all(k in data for k in ("budget", "timeline_weeks", "can_sign")),
            "model_note": summary}
```

Code decides `qualified` from handler-written fields. `complete` says whether
all three expected keys are present, rather than filling a gap from prose. The wire
key handlers emit is `set_global_data`. `set_post_prompt` puts the
`post_prompt` text in the document and the SDK adds `post_prompt_url` itself.

The record lands in an in-memory list, `DISPOSITIONS`, which a restart clears.
Your version posts it to the CRM in the same place.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/qualifier/`. The end-of-call POST goes
to the same host, so the same tunnel receives it.

## Verify it

No network, no account. The verifier drives the agent's own HTTP app with
FastAPI's test client.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders and validates the SWML, runs the handlers, POSTs to the agent's own
`/post_prompt` route, and asserts the following.

- each handler emits exactly `set_global_data` with its one field
- a value of the wrong type or sign gets `INVALID` and no action, including a boolean where an integer is due
- the document carries a `post_prompt` and a `post_prompt_url` on this agent's route, with credentials and a `__token` in the URL
- the basic-auth gate refuses a POST without credentials, and no record is written
- a POST whose summary and `call_log` contradict all three fields yields qualification fields equal to `global_data`
- in that record the model's words appear only in `model_note`
- a POST whose `global_data` lacks `can_sign` yields `can_sign: null`, `qualified: false`, `complete: false`

## Limitations

`post_prompt_url` is a URL the SDK builds from its own host, carrying the
basic-auth credentials and a per-call token. The platform must reach it, which
on a laptop means the same tunnel as the webhook.

The record keeps the model's summary as `model_note`. Delete that line if your
CRM must never hold model prose.

## What to change first

In `on_summary`, replace `data.get("budget")` with a value read from the summary
and run the verifier. The contradiction test fails: the record now says two
million, which is the failure this recipe exists to prevent.
