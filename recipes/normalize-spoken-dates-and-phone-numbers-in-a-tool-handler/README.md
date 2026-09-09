# Normalize spoken dates and phone numbers in a voice AI tool handler

> The tool takes "next Tuesday" and "four one five, five five five, oh one two three" as the caller said them. The handler turns them into an ISO date and an E.164 number, writes those to `global_data`, and reads both back in words the caller can check.

**Scenario:** a repair shop scheduling a callback by phone

## What this demonstrates

Speech recognition does not produce dates and phone numbers. It produces
words: "the fifth of March", "9/30", "oh one two three". Asking the model to
convert them is asking it to guess, and a guess about a callback number is a
missed callback. This tool takes both values in the caller's words and the
handler does the conversion in code.

Three things follow from that. The parameter descriptions carry examples of
the words, not a format, so the model passes what it heard. The handler writes
the machine values, `2026-09-15` and `+14155550123`, to `global_data`, where
the next tool or the post-prompt reads them. And the handler reads both back
in words, with the weekday, so a wrong date is caught by the caller before it
is booked. When it cannot read a value it says so with a typed state and asks
for the one piece it needs.

## How it works

```python
@AgentBase.tool(name="schedule_callback", parameters={
    "type": "object",
    "properties": {
        "date": {"type": "string", "description": "The day in the caller's words: "
                 "'tomorrow', 'next Tuesday', 'the fifth of March', 'March 5th', '9/30'."},
        "phone": {"type": "string", "description": "The number as spoken or read: "
                  "'four one five, five five five, oh one two three' or '(415) 555-0123'."},
    }, "required": ["date", "phone"]})
def schedule_callback(self, args, raw_data):
    when = normalize_date(args.get("date"), today())
    if when is None:
        return FunctionResult(f"UNPARSED_DATE: could not read {args.get('date')!r} ...")
    number = normalize_phone(args.get("phone"))
    ...
    result = FunctionResult(f"Callback set for {spoken_date(when)} at "
                            f"{spoken_phone(number)}. Read both back ...")
    result.update_global_data({"callback": {"date": when.isoformat(), "phone": number}})
    return result
```

The date grammar is small and stated. "Today", "tomorrow" and "the day after
tomorrow" are relative. A bare weekday is the next one after today, so
"Saturday" on a Saturday is a week away; "next" adds a week. A month and an
ordinal day, as words ("the twenty second of September"), digits ("22nd") or
`9/30`, mean the next time that date comes round. A year makes it absolute.
Cardinal day words ("March five") are not in the grammar. Anything
else, and a day that does not exist in its month, is `UNPARSED_DATE`.

Phone numbers are the digits found among the words, with "oh" and "o" as
zero. Ten digits get `+1`; eleven starting with a one get `+`; anything else is
`UNPARSED_PHONE`. The read-back groups the digits three, three, four, as a
person would say them.

What "next Tuesday" and "(415) 555-0123" return on Saturday 5 September 2026:

```json
{"response": "Callback set for Tuesday, September 15th at four one five, five five five, zero one two three. Read both back and ask the caller to confirm.",
 "action": [{"set_global_data": {"callback": {"date": "2026-09-15", "phone": "+14155550123"}}}]}
```

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py                    # serves /callback/ and /callback/swaig
```

The TypeScript surface is the same agent with `defineTool`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point a number's SWML webhook at `https://<user>:<password>@<your-host>/callback/`
and call it. Say a day and read out a number; the agent reads both back.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

With today pinned to Saturday 5 September 2026 through `TODAY`, the verifier
renders the document and runs thirteen pairs through the handler. It asserts
the following.

- one tool on each surface, `date` and `phone` both required, and both descriptions carry the spoken examples
- "tomorrow", "today", "Tuesday" and "next Tuesday" become the 6th, the 5th, the 8th and the 15th of September, each read back with its weekday
- "Saturday", said on a Saturday, is the 12th, not today
- "the fifth of March" and "March 5th" both become `2027-03-05`; "September 30", "9/30" and "the twenty second of September" stay in 2026
- the same number in seven spellings, spoken and written, one with the leading one, all become `+14155550123` and are read back as grouped words
- every success writes `callback.date` and `callback.phone` to `global_data` as one action
- "someday soon" and "February 30" are `UNPARSED_DATE`; a seven digit number is `UNPARSED_PHONE`, each with no action
- the TypeScript surface, through its own `/swaig` route with the documented `argument` shape, gives the same thirteen results

## Limitations

The grammar is North American English and one country code. "Next Tuesday"
means a week after the coming Tuesday here; some callers mean the coming one.
State the rule your callers expect, and keep the read-back, which is what
catches the difference either way.

Times of day are not parsed. Add them as a third parameter with the same
shape: words in, a typed state out when the words do not resolve.

A year makes a date absolute even when it is in the past. "February 29"
resolves only when this year or next is a leap year. Ten digits are taken as a
North American number with no check on the area code. Each is one line to
tighten once you know your callers.

The TypeScript SDK's `/swaig` route in 2.0.5 hands `argument` to the handler
as posted, while the platform nests the arguments in `argument.parsed[0]`. The
surface overrides `onFunctionCall` to unwrap that shape.

## What to change first

Change `or 7` to `or 0` in the Python weekday arithmetic (`|| 7` in the
TypeScript) and run the verifier. The "Saturday" row fails, because a Saturday
now means today rather than a week away. Every other weekday row still passes,
which shows exactly which rule the change touched.
