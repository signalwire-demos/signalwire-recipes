# Route calls by dialed number or time

> One SWML webhook serves several numbers. Your handler reads the dialed number from the documented inbound call webhook and the clock in that line's zone. It returns the document for that number at that hour.

**Scenario:** a bike shop with a sales line in Denver and a workshop line in Los Angeles, both pointed at one URL

## What this demonstrates

SignalWire fetches SWML with a POST the vendored REST spec documents as the
inbound call webhook. Its `call` object requires `call_id`, `direction`,
`type`, `from`, `to` and six more fields, and carries `to_number` for phone
calls. The spec describes `to` as "The number/URI of the destination of this
call". This handler computes a document per request. It keys a table of lines by dialed number and judges the clock in the
line's own time zone with `zoneinfo`. It builds one of three documents with
`SWMLService`: greet and `connect`, play the hours and hang up, or not in
service.

## How it works

```python
def document(to, now):
    service = SWMLService(name="front", route="/swml")
    service.add_verb("answer", {})
    line = LINES.get(to)
    if not line:
        service.add_verb("play", {"url": f"say:{UNKNOWN}"})
    elif is_open(line, now):
        service.add_verb("play", {"url": f"say:{line['greeting']}"})
        service.add_verb("connect", {"to": line["connect"], "timeout": CONNECT_TIMEOUT})
    else:
        service.add_verb("play", {"url": "say:" + CLOSED.format(...)})
    service.add_verb("hangup", {})
    return service.get_document()

@app.post("/swml")
def swml():
    payload = request.get_json(force=True)
    return jsonify(document(dialed(payload["call"]), datetime.now(timezone.utc)))
```

What the platform sends, and what it gets back for an open line:

```http
POST https://<your-host>/swml
{"call": {"call_id": "...", "type": "phone", "from": "+1555...", "to": "+15550001111",
          "to_number": "+15550001111", ...}, "vars": {}, "envs": {}, "params": {}}

{"version": "1.0.0", "sections": {"main": [
  {"answer": {}}, {"play": {"url": "say:Ridgeline Cycles sales, one moment."}},
  {"connect": {"to": "+15550100001", "timeout": 25}}, {"hangup": {}}]}}
```

`dialed()` prefers `to_number`, which the spec says is present for phone
calls, and falls back to `to` for SIP and WebRTC. The hours live on the line,
so two lines in two zones read one clock and get two answers.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: the basic-auth pair, and the connect timeout
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Put your own numbers, zones, hours
and destinations in `LINES`, then point every one of those numbers' SWML
webhooks at `https://<user>:<password>@<your-host>/swml`, with the pair from
`.env`. Call each and listen for its greeting.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You drive the Flask app with its test client and a frozen clock, and assert
the following.

- the fixture carries every field the spec's inbound call webhook requires, at both levels, and nothing the spec lacks
- the spec describes `to` as the destination, and `phone` is in the type enum
- a request without the basic-auth pair, or with the wrong password, gets 401 and no document
- at 16:30 UTC each of the two numbers gets `answer`, `play`, `connect`, `hangup`
- each carries its own complete greeting and its own `connect` destination and timeout
- at 01:00 UTC each gets `answer`, `play`, `hangup`, with its own hours in the message
- two instants one minute apart, 15:59 and 16:00 in Los Angeles, fall on opposite sides of the workshop's close
- at the same two instants Denver stays open, so the zone on the line decides
- a number in neither line gets the not-in-service message and no `connect`
- every document validates against the bundled schema, and `dialed()` prefers `to_number` over `to`

## Limitations

You prove the documents against a frozen clock. What the caller hears, and
whether the destination answers, are the platform's side of a live call.

The table is a dictionary and the hours are one window a day. Holidays,
lunch breaks and per-day schedules are yours to model; the branch point stays
the same.

## What to change first

Change the workshop's `tz` to `America/Denver` and run the verifier. The 15:59
edge case fails, because 22:59 UTC is 16:59 in Denver and the workshop closes
at 16:00. The zone belongs to the line, and the verifier holds each line to its
own.
