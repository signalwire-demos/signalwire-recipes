# Start from a prefab AI agent

> A complete receptionist or survey agent runs from a prefab class and a short configuration block.

**Scenario:** a bicycle shop's front desk and its workshop follow-up survey

## What this demonstrates

The SDK ships complete agents as classes. You pass configuration, not a prompt.
The prefab writes its prompt sections and registers its tools with their
handlers. The receptionist also sets its voice and wires its transfer.
`ReceptionistAgent` takes a list of departments; `SurveyAgent` takes a list of
typed questions.

What you configure becomes enforcement. The department names become an `enum` on
the transfer tool's `department` argument, and the handler refuses a value that is
not on the list. A rating question's `scale` becomes the bound the validator
applies.

## How it works

```python
ReceptionistAgent(
    departments=[
        {"name": "sales", "description": "Pricing, availability and new orders",
         "number": "+15551230001"},
        {"name": "workshop", "description": "Repairs, servicing and appointments",
         "number": "+15551230002"},
    ],
    greeting="Ridgeline Cycles, how can I help?",
)
```

The rendered document carries two tools you did not write, `collect_caller_info`
and `transfer_call`, and a prompt you did not write. It sets the voice
`rime.spore` and `transfer_summary` in `params`. The departments sit in
`global_data`. The transfer tool's `department` parameter is
`{"enum": ["sales", "workshop"]}`. On a transfer the handler emits a `connect`
verb for the department's number with `transfer: "true"` and `post_process: true`.

```python
SurveyAgent(
    survey_name="Workshop follow-up",
    questions=[{"id": "rating", "type": "rating", "scale": 5,
                "text": "From one to five, how would you rate the work?"}, ...],
)
```

The survey registers `validate_response` and `log_response`, sets a `post_prompt`,
and rejects a rating of seven on a five-point scale. The constructor accepts
four question types: `rating`, `multiple_choice`, `yes_no` and `open_ended`. It
fills in a `scale` of five for a rating that has none. It raises for a multiple
choice question with no `options`, and carries one with `options` into
`global_data` as written.

`PREFAB` chooses which one this process serves. `app.py` builds both so the
verifier can prove both.

The TypeScript prefabs take the same configuration in camel case
(`surveyName`, `brandName`) and render the same tools, enum and voice. The
survey registers three more tools for reading progress: `answer_question`,
`get_current_question` and `get_survey_progress`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD and the numbers
python app.py                    # PREFAB=survey python app.py for the other
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/reception/` or `/survey`.

The TypeScript surface is the same two prefabs on `@signalwire/sdk`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start                       # PREFAB=survey npm start for the other
```

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

It builds both agents, renders and validates each, and asserts the following.

- the receptionist exposes `collect_caller_info` and `transfer_call`, sets `transfer_summary`, and sets the voice `rime.spore`
- the department enum equals your list; a transfer's whole result equals the expected payload: `connect` to the configured number with `transfer: "true"`
- the handler refuses an unlisted department with the prefab's exact message and dials nothing
- the survey exposes `validate_response` and `log_response`, sets a `post_prompt`, and carries your questions with their types and scale
- the validator refuses a rating of seven; a four returns the prefab's exact valid and recorded messages
- a rating without `scale` gets five; a multiple choice without `options` raises `ValueError`, and one with `options` renders them as written
- the TypeScript prefabs render the same tools, enum and voice, and their handlers, driven through their own `/swaig` routes, return the same transfer, refusal and validation results

## Limitations

A prefab is a starting point with opinions. The receptionist takes `voice` as a
constructor argument, but its prompt text and tool descriptions are its own.
`SurveyAgent` has no `voice` argument at all. When the configuration surface stops
fitting, write the agent directly; the prefabs are short and readable in
`signalwire/prefabs/`.

The receptionist hands the configured `number` to `connect` unchanged, so the
verifier proves the transfer for a phone number and nothing else.

The platform posts a tool's arguments as `argument: {parsed: [args], raw}`. The
TypeScript SDK's `/swaig` route in 2.0.5 hands `argument` to the prefab's
handlers as posted, so they would read `parsed` and `raw` instead of the
caller's name. The surface subclasses each prefab and overrides
`onFunctionCall` to unwrap the documented shape before dispatch.

## What to change first

Add `{"name": "legal", ...}` to `DEPARTMENTS` and run the verifier. The enum
assertion fails, which is the point: the enum comes from your list, and the
transfer tool's valid arguments are exactly the departments you configured.
