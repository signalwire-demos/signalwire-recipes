# Forward an inbound SMS to other numbers

> A text arriving on your number goes on to each number on a list as its own `reply`, prefixed with the sender and sent from the number that received it. `reply`'s `to` defaults to the sender, so naming `to` is what makes it a forward.

**Scenario:** a shop's public number forwards customer texts to the two people on shift

## What this demonstrates

The inbound message webhook carries `from`, `to` and `body`, and the spec
requires all three. The handler answers with a Messaging SWML document holding
one `reply` for every recipient on the list. `to` is the recipient, `from` is
the number the text arrived on, and the body is the sender's number, a colon,
and their words.

`reply` is the method that sends a message from a messaging document. Its `to`
defaults to `message.from` and its `from` to `message.to`, so a `reply` with no
`to` answers the sender. Naming `to` sends it somewhere else, which is why the
reference's own example of this carries the heading "Forward an inbound message
to another number".

Three rules keep it a forwarder rather than a loop. The sender is left out, so
the team can talk on the same line. The receiving number is left out, because
texting the line that fired this webhook fires it again. A repeated entry in
the list sends one copy, not two.

## How it works

```python
def forward_document(sender, received_on, body, recipients=None):
    steps = []
    if keyword(body) not in STOP_WORDS:
        for recipient in targets(sender, received_on, recipients):
            # `to` is what makes this a forward rather than a reply
            steps.append({"reply": {"to": recipient, "from": received_on,
                                    "body": forwarded_body(sender, body)}})
    return {"version": "1.0.0", "sections": {"main": steps}}
```

What a customer's text renders, with two people on shift:

```json
{"version": "1.0.0", "sections": {"main": [
  {"reply": {"to": "+15550100001", "from": "+15550001111",
             "body": "+14155550123: Is my bike ready?"}},
  {"reply": {"to": "+15550100002", "from": "+15550001111",
             "body": "+14155550123: Is my bike ready?"}}]}}
```

Two limits shape the body. An SMS body maxes out at 1600 characters, and the
sender prefix counts, so a full-length inbound is truncated to leave room.
A STOP is not forwarded at all. The carrier keywords are an opt-out from you,
not a message for the team, and `handle-opt-outs-yourself` is where they go.
The match is the trimmed, lowercased word with trailing punctuation removed,
so `STOP.` counts and `stop please` does not.

The Messaging method set is `reply`, `receive`, `execute`, `return`,
`transfer`, `goto`, `label`, `switch` and `request`. `send_sms` is not in it;
that is the Calling method for texting from inside a call, which
`text-the-caller-during-the-call` uses.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # basic auth and FORWARD_TO, comma separated
python app.py                    # serves POST /inbound on :8080
```

The TypeScript surface is the same handler on `node:http`, on Node 20.18.1 or
newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point the number's message handler at `https://user:pass@your-host/inbound`
and text it.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the route with payloads shaped like the spec's inbound
message webhook. The configured list carries a repeat and the receiving line,
so the ordinary rows exercise both guards. It asserts the following.

- every document is checked against the documented Messaging method set, not the bundled schema, which is the Calling one and would accept the wrong method
- a customer's text renders one `reply` per recipient with `to`, `from` the receiving line, and the prefixed body
- the sender, the receiving line and the repeated entry are each left out, so two people on shift get one copy each
- a text from one recipient renders one `reply`, to the other
- a 1600 character body is truncated so the whole message is exactly 1600 with the prefix
- a media-only text forwards the prefix and nothing more
- "STOP." with stray spaces renders an empty document
- the payload carries every field the spec requires, and the spec requires `from`, `to` and `body`
- a payload missing `from` or `to` is a 400, and a post without credentials is a 401
- the TypeScript surface renders the same five documents and the same two refusals

## Limitations

The verifier proves the document, not delivery. A forwarded text from a 10DLC
number is A2P traffic and needs a registered campaign, and the receiving line
must be messaging-enabled to be a `from`.

Two forwarders pointed at each other stop, because each one drops the sender.
A ring of three does not: every hop's sender is the previous line, never the
next one. Do not point one of these at another.

Media is dropped. An inbound MMS carries `media` URLs in the payload, and
`reply` takes a `media` list of up to eight attachments. Carrying them over is
the first extension; the URLs are platform-hosted and unguessable.

Recipients are a list in the environment. A roster that changes by shift is a
lookup in `targets`, which is the one function that decides who gets a copy.

## What to change first

Delete `"to": recipient` from the `reply` and run the verifier. The document
is still a valid Messaging document and the assertion fails. That is the
point: without `to`, `reply` answers the sender, and the forwarder becomes an
echo.
