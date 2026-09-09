# Handle SMS STOP and START in your own code

> Your webhook handler records a STOP from the inbound message webhook and confirms it with a `reply` document. Every later send checks that record before it makes a request, so a refused send is never a request.

**Scenario:** a bike shop that texts repair updates and must stop the moment a customer says so

## What this demonstrates

SignalWire does not manage opt-outs for you. The platform messaging page says
"Customers are responsible for handling inbound stop requests and removing
those customers from subscriber lists". It adds that messages should not go
out again "unless they have opted back in via an Unstop request". The page is
https://signalwire.com/docs/platform/messaging. So the record lives on your
side, and two pieces of your code keep it. One is the handler that receives
the inbound message webhook, behind the platform's signature. The other is the
send path that consults the record before it builds a request.

The vendored REST spec documents the inbound message webhook. SignalWire POSTs
a JSON body whose `message` object carries `from`, `to`, `body`, `type` and
seven more required fields, and it expects a SWML document in reply.

## How it works

```python
def handle_inbound(message):
    word = keyword(message.get("body"))          # trim, lowercase
    sender, ours = message["from"], message["to"]
    if word in STOP_WORDS:
        OPT_OUTS[sender] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return reply(ours, sender, STOPPED)
    if word in START_WORDS:
        OPT_OUTS.pop(sender, None)
        return reply(ours, sender, RESUMED)
    return {"version": "1.0.0", "sections": {"main": []}}

def send(to, body):
    if to in OPT_OUTS:
        raise OptedOut(f"{to} opted out at {OPT_OUTS[to]}; no message sent")
    return http.post("/api/messaging/messages", body={"to": to, "from": FROM, "body": body})
```

What the handler returns for a STOP:

```json
{"version": "1.0.0", "sections": {"main": [
  {"reply": {"to": "+1555YYYYYYY", "from": "+1555XXXXXXX",
             "body": "You are unsubscribed from Ridgeline Cycles messages. Reply START to opt back in."}}]}}
```

Before any of that runs, a `before_request` hook checks SignalWire's signature
over the request, `hex(HMAC(signing_key, url + raw_body))` in
`X-Signalwire-Signature`, and answers 403 without it. Anyone can reach a public
webhook, and a forged START would undo a real STOP. The check is the one
`verify-a-webhook-signature` explains. The keyword compares whole, after trim
and lowercase, so "can you stop calling" is a message and "Stop" is an opt-out. The confirmation goes out through the
document rather than through `send`, because it is the one message an opted-out
number should still receive. Anything that is not a keyword gets an empty
document, which sends nothing and records nothing.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, SMS_FROM, the signing key and INBOUND_URL
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Set the number's message handler to
a SWML script at `https://<your-host>/inbound`, and put that same URL in
`INBOUND_URL`. Text STOP to it, then ask the
same process to send, and read the 403:

```bash
curl -X POST http://localhost:8080/send -H 'Content-Type: application/json' \
     -d '{"to": "+1YYYYYYYYYY", "body": "Your bike is ready."}'
```

The record is in that process, so the send has to go through it. `/send` is
your send path with no authentication of its own; put yours in front of it.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier drives the Flask app with its test client and swaps the SDK's HTTP
layer for a recorder. It asserts the following.

- the fixture carries every field the spec's inbound message webhook requires, at both levels, and no field the spec lacks
- an inbound webhook with no signature, or a wrong one, is refused with 403 and records nothing, even when its body says START
- a plain message answers with a document that validates and holds no verbs, and records nothing
- " Stop " answers with a document whose one method is `reply` from the receiving number to the sender with the exact confirmation text, and the handler records the sender
- every document is checked against the documented Messaging method set, because the bundled schema is the Calling one, which refuses `reply` and accepts `send_sms`
- `send` to that number raises `OptedOut` naming it, and the recorder saw no request; `POST /send` for it answers 403 with the reason
- `send` to another number makes one `POST` to the documented messages path with exactly `to`, `from` and `body`; `POST /send` for it answers 202
- "START" answers with the exact resume text, clears the record, and the next `send` to that number goes out
- each of the six keywords records the sender in lower, upper and mixed case; a sentence containing one does not

## Limitations

The record is a dictionary in the process. Replace `OPT_OUTS` with your
database before anything depends on it.

The keyword list is this recipe's. Which words your traffic must honour, and
what the confirmation must say, are questions for your carrier agreements and
your counsel, not for the platform.

## What to change first

In `send()`, move the `http.post(...)` call above the `if to in OPT_OUTS`
check, keep its result in a variable, and return that after the check. Run the
verifier. The refusal assertion fails because the recorder saw a request, which
is the failure this recipe exists to prevent.
