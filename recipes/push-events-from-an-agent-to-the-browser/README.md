# Push events from a voice AI agent to the browser

> A tool result carries a SWML `user_event` whose `event` is any JSON object the handler chooses. The bundled schema describes the verb as sending events to the connected client on the call.

**Scenario:** a booking page that highlights the slot the caller picked, the moment the agent records it

## What this demonstrates

`FunctionResult.swml_user_event(event)` wraps a `user_event` verb in a one-verb
SWML document and adds it as a `SWML` action on the tool result. The bundled
schema says `user_event` "allows the user to set and send events to the
connected client on the call". It notes the verb is "commonly used with the
browser-sdk" and that "the event object can be any valid JSON object". The
handler validates the supplied slot id and chooses the event payload. The
result carries the `event` as data and a `response` string as text, and the
verifier asserts both exactly.

## How it works

```python
def select_slot(self, args, raw_data):
    slot = args.get("slot")
    if slot not in SLOTS:
        return FunctionResult("INVALID: that slot is not on the page.")
    return FunctionResult(f"Noted {SLOTS[slot]} for the caller.").swml_user_event(
        {"type": "slot_selected", "slot": slot, "label": SLOTS[slot]})
```

The function result the platform receives:

```json
{"response": "Noted Thursday 2pm for the caller.",
 "action": [{"SWML": {"version": "1.0.0", "sections": {"main": [
   {"user_event": {"event": {"type": "slot_selected", "slot": "thu-14",
                             "label": "Thursday 2pm"}}}]}}}]}
```

`user_event` requires `event`; the schema rejects the verb without one. The
`slot` parameter carries an `enum` of the ids on the page. The handler returns
no action for an id outside `SLOTS`. A valid id the model supplies wrongly
still emits the event: the check bounds the ids, not the model's accuracy.
Nothing here reserves the slot; the event reports a choice.

The `swml/` surface places a `user_event` in a plain document before the `ai`
verb. Your backend can push the same shape mid-call with the REST command
`calling.user_event`. The vendored REST spec's variant for that command
requires `command`, `id` and `params`, and `event` is the one required key in
`params`. The verifier reads that from the spec.

## Run it

This recipe is the agent side. The page side is outside it: a Browser SDK
client that dials an address and subscribes to user events. The
[Browser SDK reference](https://developer.signalwire.com/sdks/reference/browser-sdk/)
covers that client.

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook, or a
Fabric address's SWML handler, at
`https://<user>:<password>@<your-host>/booking/`. Dial that number or address
from your Browser SDK page, pick a slot by voice, and watch the page.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders and validates the SWML, runs the handler, and asserts the following.

- the tool's `slot` parameter carries the three slot ids as an `enum`
- a valid slot returns the exact payload: one `SWML` action holding one `user_event` with the exact `event` object, and the exact `response`
- that inline document validates against the bundled schema
- a `user_event` with no `event` fails the schema
- an unknown slot returns `INVALID` with no action
- the REST spec's `calling.user_event` variant requires `command`, `id` and `params`, with `event` the one required key in `params`
- the plain-SWML surface validates and its verbs are `answer`, `user_event`, `ai`, with the exact event

## Limitations

The verifier proves the document. How a page receives the event is the client
side of a live call. The Browser SDK's documentation covers the call a page
subscribes with.

The schema gives `user_event` no result variable. If the page must acknowledge,
have it call your backend.

## What to change first

Remove `"label": SLOTS[slot]` from the event and run the verifier. The exact
payload assertion fails. On a live call the page would have to look the label
up itself, so put in the event everything the page needs to render.
