# Collect required details in any order with a voice AI agent

> A caller gives the details of a report in whatever order they come to mind. One tool records each detail into `global_data` and says what is still missing; the submit tool reads the same `global_data` and refuses until every required detail is present.

**Scenario:** an employee absence reporting line for a warehouse

## What this demonstrates

A form has required fields, and a phone call does not fill them in order.
The caller says why they are out before they say who they are. This agent
takes the details as they come. `record_detail` takes a field name and a
value and writes the whole details object back with `set_global_data`. Its
response tells the model what is still needed, in the words the checklist
uses, so the model asks for that and nothing already recorded.

`submit_report` takes no arguments. It reads the collected details from the
`global_data` the platform posted with the call, and it files the report only
when every required field is there. A model that asks to submit early gets a
`MISSING` list, not a report. The prompt says "record each detail as soon as
you hear it"; the handlers are what make the order not matter.

## How it works

```python
REQUIRED = {"employee_name": "the employee's name",
            "shift_date": "the date of the shift",
            "reason": "the reason for the absence"}

def record_detail(self, args, raw_data):
    field, value = _text(args.get("field")), _text(args.get("value"))
    details = dict((raw_data.get("global_data") or {}).get("details") or {})
    details[field] = value
    result = FunctionResult(f"Recorded {FIELDS[field]}. {status_line(details)}")
    result.update_global_data({"details": details})   # the whole object
    return result

def submit_report(self, args, raw_data):
    details = (raw_data.get("global_data") or {}).get("details") or {}
    if missing(details):
        return FunctionResult("MISSING: " + ", ".join(...) + ". Ask for those.")
    ...
```

The `field` parameter is an enum of the checklist, so the model is offered
the field names rather than inventing them. The enum shapes the offer only:
an out-of-enum value still reaches the handler, which answers `UNKNOWN_FIELD`
and writes nothing.

`set_global_data` merges top-level keys. Writing `{"details": {"reason": ...}}`
would replace the whole object and lose the fields already recorded. So the
handler reads the current object from the request, adds the one field, and
writes the whole object back. The verifier threads `global_data` between calls
the way the platform does, applying each action before the next call.

`submit_report` also reads `report_id` from `global_data`. Once a report is
filed, asking again, or a retry of the same call, gets `ALREADY_FILED` with
the reference and no second report.

What the first `record_detail` returns, with the reason given first:

```json
{"response": "Recorded the reason for the absence. Still needed: the employee's name, the date of the shift.",
 "action": [{"set_global_data": {"details": {"reason": "a fever"}}}]}
```

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py                    # serves /absence/ and /absence/swaig
```

The TypeScript surface is the same agent with `defineTool`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point a number's SWML webhook at `https://<user>:<password>@<your-host>/absence/`
and call it. Give the reason first, then the date, then your name, and ask it
to submit after each one.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier renders the document, then runs the handlers in a scrambled
order, threading `global_data` between calls the way the platform does. It
asserts the following.

- both tools render; the `field` enum equals the checklist and `submit_report` has no parameters
- reason first, with stray spaces: the trimmed value is written, and the response names the two fields still needed
- submit with two fields missing is refused with exactly those two, and writes nothing
- an optional note, sent as a number, is recorded as text and does not shorten the missing list
- the date next: one field still needed, and the details object now holds all three
- an unknown field, the prototype name `constructor`, and an empty value are refused with a typed state and no action
- the name last: the response says everything required is in; submit then files `ABS-1001` and writes `report_id`
- a second submit answers `ALREADY_FILED` with the reference, writes nothing, and the report list still holds one
- the TypeScript surface, through its own `/swaig` route with the documented `argument` shape, gives the same twelve responses and actions

## Limitations

The report is filed into a list in the process. Your HR system replaces it.
The `report_id` check makes a retry within the call harmless; a retry after
the call has ended is your system's idempotency key to keep.

Two `record_detail` calls emitted in one model turn would each read the same
`global_data`, and the second whole-object write would drop the first field.
Whether the platform applies one action before the next call in the same turn
is not something this verifier can prove. The prompt asks for one detail per
call for that reason.

Optional fields are recorded the same way but never block the submit. Whether
a detail is required is a line in `REQUIRED`, not a prompt sentence.

The TypeScript SDK's `/swaig` route in 2.0.5 hands `argument` to the handler
as posted, while the platform nests the arguments in `argument.parsed[0]`. The
surface overrides `onFunctionCall` to unwrap that shape.

## What to change first

Move `reason` from `REQUIRED` to `OPTIONAL` and run the verifier. The first
submit still refuses, but for one field, and the expected `MISSING` line no
longer matches. The checklist is code, and the verifier reads it as code.
