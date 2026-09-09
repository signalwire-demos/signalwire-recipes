# Get recording consent before recording

> Recording starts from the consent tool's result, so it cannot start before
> the caller agrees.

**Scenario:** a credit union taking account queries

## What this demonstrates

The document contains no `record_call`. Recording begins only when the consent handler
emits one, and it emits one only for an exact match against a set of agreements. A
refusal moves the call on without recording, and anything else does neither.

In a two-party consent jurisdiction the refusal path is the one that has to work, so
anything short of a clear yes is not consent. What the recipe cannot do is hear the
call. The handler judges the string the model extracted, which makes faithful
transcription a trust boundary rather than a guarantee.

## How it works

Two things keep recording behind the disclosure, and they are worth different
amounts.

The **hard one** is where the recording action comes from. Nothing in the
document records; the only `record_call` on the whole agent is built inside the
consent handler.

```python
return (
    FunctionResult("Thank you. Starting the recording now.")
    .update_global_data({"recording": "consented"})
    .record_call(control_id="consented", stereo=True, direction="both")
    .swml_change_step("assist")
)
```

`record_call()` on a `FunctionResult` wraps its verb in a `SWML` action, so what
the platform receives is a document fragment containing `record_call`, not a
method name. The account tool also lives on a later step, so it is not on the
table while the question is still being asked. Both of those are code.

The **soft one** is the flow itself. `set_step_criteria()` reads like a gate, but it
is a sentence the model judges, and `valid_steps` shapes a navigation tool rather than
locking a door. Neither keeps a caller out of the next step, so `get_balance` checks
that the recording question was answered before it answers anything. A step is a place
in a flow, not a security boundary.

The handler compares the whole normalised answer against a refusal set, then an
agreement set. Whole answers, not substrings: `yesterday` contains `yes`, and so does
`I can't say yes`. Contractions are expanded before apostrophes go, so `that's fine`
and `that is fine` are one answer. Hedges are left alone, because dropping `perhaps`
would turn `perhaps, sure` into consent. Anything matching neither set returns
`UNCLEAR` and emits no action.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at
`https://<user>:<password>@<your-host>/intake/`, using the credentials you set.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and runs the handler, asserting:

- `record_call` appears nowhere in the document
- the disclosure step exposes only `record_consent`
- a yes emits `record_call` in stereo on both directions, plus `change_step`
- a no moves on and emits no recording
- seven non-answers emit no recording and no transition, including
  `yesterday`, `I can't say yes` and `perhaps, sure`
- real refusals and real agreements still land on the right side
- `get_balance` refuses until the question has been answered

## Limitations

Consent is matched against fixed answer sets. That is thin for production: a caller
who says something neither set contains is asked again, which is safe but blunt. A
real deployment keeps the utterance alongside the recording, and has the disclosure
wording reviewed by someone qualified to review it.

Nothing here stops a caller withdrawing consent later. That needs
`stop_record_call` on a second tool, keyed to the same `control_id`.

## What to change first

Move `record_call` out of the handler and into the document, above the `ai`
verb. Everything still works, and the recording now starts while the disclosure
is still being read.
