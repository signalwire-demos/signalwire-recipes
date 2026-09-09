# Run an SMS survey over several messages

> A survey is one outbound text and then a conversation the platform does not hold for you. Each reply arrives at your webhook on its own, so the state that says which question a number is on lives with you, keyed by the sender.

**Scenario:** a bike shop texts three questions after every service visit and keeps the answers by phone number

## What this demonstrates

Every inbound text is a fresh webhook with no memory of the last one. A survey
is therefore a small state machine of your own. The sender's number is the key,
the step is the value, and the reply you return is the next question. This
recipe keeps that state in a file, advances it one reply at a time, and answers
with a messaging SWML `reply`.

Four things the handler does that a survey needs.

- An answer that does not fit the question is re-asked, and the step does not
  move.
- The last answer gets a closing line, and any text after that gets an empty
  document: nothing sent, nothing recorded.
- STOP, or any of the other stop words, marks the number and ends the survey.
  A number that has stopped is never texted a first question, and the refusal
  happens before any request is made.
- The webhook checks the platform's signature before it touches state, because
  an unsigned POST could otherwise fill your survey with anything.
- A webhook delivered twice gets the same reply twice and moves nothing, even
  when the retry is late or the survey is already complete. The record keeps
  every `message_id` it acted on, with the reply it gave. Without that, a
  retried rating would be parsed at the comment step and stored as the comment.
  A retry that arrives after STOP gets silence, not the cached question.
- `/begin` sends texts at your expense, so it is behind a key the server holds
  and your systems present as `X-Survey-Key`. The public internet gets a 403.

The vendored REST spec documents the inbound payload as `{message, vars,
params}`, where `message` carries `from`, `to` and a `body` that may be null.
The first question goes out as `POST /api/messaging/messages`, which requires
`to` and `from`.

## How it works

```python
def handle_inbound(message):
    sender = message["from"]
    state = _load()
    record = state.get(sender)
    word = keyword(message.get("body"))
    if word in STOP_WORDS:
        state[sender] = {**(record or {"step": 0, "answers": {}}), "stopped": True}
        _save(state)
        return reply(STOPPED)
    if not record or record["stopped"] or record["step"] >= len(QUESTIONS):
        return silence()
    key, _, kind = QUESTIONS[record["step"]]
    answer = parse(kind, message.get("body"))
    if answer is None:
        return reply(REASK.get(kind, QUESTIONS[record["step"]][1]))
    record["answers"][key] = answer
    record["step"] += 1
    _save(state)
    return reply(DONE if record["step"] == len(QUESTIONS) else QUESTIONS[record["step"]][1])
```

What the webhook returns after a valid first answer:

```json
{"version": "1.0.0",
 "sections": {"main": [{"reply": {"body": "Would you recommend us to a friend? Reply YES or NO."}}]}}
```

`parse` is where the survey stops being a chat. A rating is one of five digits
after trim; yes or no accepts `y` and `n`; the comment accepts anything and
treats `SKIP` as an empty answer. Anything else returns `None`, and the same
question comes back.

The state is a JSON file keyed by number, written through a rename so a crash
mid-write leaves the old file intact. In your app that is a table with the
number as the key. The two documented commands, the server and `begin`, are two
processes, which is why the state cannot live in a dictionary.

The TypeScript surface is the same handler on `@signalwire/sdk`, with a small
`node:http` server for the two routes.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, and the three below
python app.py                    # serves POST /inbound and POST /begin on :8080
python app.py begin +14155550123 # texts the first question
```

Or the TypeScript surface, on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start                        # the same two routes
```

Point the number's message handler at your public `/inbound` URL, and put that
exact URL in `INBOUND_URL`: the signature is computed over the URL as
SignalWire called it. `SMS_FROM` is that number, and
`SIGNALWIRE_SIGNING_KEY` is the project's signing key. `SURVEY_ADMIN_KEY` is
whatever your own systems will send as `X-Survey-Key` when they start a survey.

Survey traffic from a 10DLC number needs a registered campaign; see
[Register a 10DLC brand and campaign](../register-a-10dlc-brand-and-campaign/).
Opt-outs are yours to honour. STOP is handled here, and in full in
[Handle SMS STOP and START in your own code](../handle-opt-outs-yourself/).

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier points the state at a temporary file, swaps the HTTP layer for a
recorder, and asserts the following.

- `begin` sends one documented `POST /api/messaging/messages` with `to`, `from` and the first question, and writes step 0
- the module is reloaded before the replies, so the state came from the file and not from memory
- a reply that does not fit is re-asked and the step stays at 0; `4`, `Yes` and a comment advance through the second and third questions to the closing line, and the three answers are on disk
- a text after the last question, and a text from a number not in a survey, each get an empty document and change nothing
- STOP marks the number, a second `begin` for it raises with no request made
- the Flask route returns 403 to an unsigned POST and 200 to one signed with the documented HMAC
- the same `message_id` delivered twice gets the same reply and leaves the state exactly as it was, a late retry of an earlier answer does too, a retried final answer gets the closing line again, and a retry after STOP gets an empty document
- `/begin` refuses a missing or wrong `X-Survey-Key` with 403 and no request, and sends with the right one
- the TypeScript surface runs the same turns from an empty file to the same replies and state, answers a redelivered message without moving, refuses the same `begin`, and its server gates the signature and the key the same way

## Limitations

The verifier proves the handler and the requests, not delivery. Whether a
question reaches the phone, and how long a customer takes to answer, are live.

The state file is a stand-in. Two server processes sharing one file would
race; a database with the number as the key is the real version.

A survey texts people who did not text first. Consent for that is yours to
collect and record before `begin`, and the recipe does not claim otherwise.

## What to change first

Change `"4"` in the verifier's second turn to `"four"` and run it. The re-ask
comes back instead of the next question and the step stays put. That is the
point: the survey advances only on an answer it can store.
