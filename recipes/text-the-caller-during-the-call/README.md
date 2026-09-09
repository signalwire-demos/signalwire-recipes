# Text the caller during the call

> A tool result carries a SWML `send_sms` addressed to `caller_id_num`, the number the platform posts with every tool call. The model never chooses the destination: the tool has no number parameter.

**Scenario:** a workshop booking line that texts the agreed appointment time to the caller

## What this demonstrates

A tool result can carry a SWML document, and that document can run `send_sms`.
The handler in this recipe builds one with `FunctionResult.send_sms`. It
addresses the text to `caller_id_num`, which the platform posts in the body of
every tool call, and sends it from a number in your environment. The tool takes
only an `appointment` argument, so the model cannot choose where the text goes.

Docs: the [send_sms reference](https://signalwire.com/docs/swml/reference/send-sms).
The [SWAIG tool webhook](https://signalwire.com/docs/apis/rest/webhooks/ai-swaig-tool-webhook)
lists `caller_id_num` in the request body.

## How it works

```python
def text_confirmation(self, args, raw_data):
    to = (raw_data or {}).get("caller_id_num")
    if not to or not to.startswith("+"):
        return FunctionResult("NO_NUMBER: ... Read the details back instead.")
    return FunctionResult("The details are on their way to your phone.").send_sms(
        to_number=to, from_number=SMS_FROM, body=body, tags=["appointment"])
```

The function result the platform receives:

```json
{"response": "The details are on their way to your phone.",
 "action": [{"SWML": {"version": "1.0.0", "sections": {"main": [
   {"send_sms": {"to_number": "+15557654321", "from_number": "+15551230000",
                 "body": "Ridgeline Cycles: your workshop appointment is ...",
                 "tags": ["appointment"]}}]}}}]}
```

`send_sms` is the SDK method and the wire verb, inside an `action` whose key is
`SWML`. When `caller_id_num` is absent or does not start with `+`, or the
`appointment` is empty, the handler returns a response and no action, and the
platform sends nothing.

The `swml/` surface does the same in a plain document: `answer`, then `send_sms`
addressed to `%{call.from}`, then `play`. `call.from` is the caller's number in
the [SWML variables reference](https://signalwire.com/docs/swml/reference/variables),
so that document attempts a `send_sms` on every call. The agent version texts
only when the handler receives a non-empty `appointment`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD and SMS_FROM
python app.py
```

`SMS_FROM` must be a messaging-enabled number on your project; the app refuses
to start without one. To deploy the `swml/` surface instead, replace its
`from_number` placeholder first. The webhook needs a public HTTPS URL. For a
local run, expose port 3000 with a tunnel such as ngrok and use that hostname.
Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/booking/`, agree a time, and watch your
phone.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier renders and validates the SWML, runs the handler with the payload
shape the platform posts, and asserts the following.

- the tool's only parameter is `appointment`
- with `caller_id_num` present, the whole result equals the expected payload
- that payload is one `SWML` action holding one `send_sms` to that number from `SMS_FROM`, with the exact body and tag
- the inline SWML document validates against the bundled schema
- an `appointment` containing another phone number leaves `to_number` as the caller's and lands in the body
- with no caller number, or one that does not start with `+`, the response starts `NO_NUMBER` and carries no action
- with no agreed time the response starts `INCOMPLETE` and carries no action
- the plain-SWML surface validates and its `send_sms` goes to `%{call.from}`

## Limitations

The handler learns nothing about delivery. Per the reference, the verb sets
`send_sms_result` to `success` or `failed` on the call; this recipe does not
read it.

The handler sends nothing when `caller_id_num` is absent or does not start with
`+`, and tells the model to read the details aloud instead.

## What to change first

Add a `phone` property to the tool's parameters and run the verifier. The first
assertion fails, which is the point: once the model can supply a number, the
caller no longer binds the send.
