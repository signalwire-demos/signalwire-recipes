# Enforce an AI agent's next step in code

> Your code decides what happens next, so the model cannot strand or misroute
> the caller.

**Scenario:** a bicycle shop booking repair drop-offs

## What this demonstrates

No slot is booked until a bike the shop actually services has been recorded. The rule
lives in the tool handlers, which read collected state instead of asking the model
whether it collected anything. The caller may well reach the scheduling step; what
they cannot do is get a booking out of it.

`valid_steps` shapes the navigation tool the model is offered. It does not constrain
your webhook, so the handler is the last authority on the transition. It is also not a
lock, which is why the tool at the destination checks the same state again.

## How it works

Two things move the conversation, and only one of them is clamped.

The model's path is the `next_step` tool, bounded by `valid_steps` on the current
step. The other path is a handler emitting a step change, and the SDK is explicit that
this bypasses the clamp. Anything the handler emits happens. Neither path makes a step a boundary. A step is a
place in a flow, so the tool that books the slot checks for a recorded bike whatever
route reached it.

So the handler checks first:

```python
def start_scheduling(self, args, raw_data):
    recorded = (raw_data or {}).get("global_data", {}).get("bike_type")
    if recorded not in SERVICEABLE:
        return FunctionResult(
            "NOT_READY: no serviceable bike has been recorded yet. Ask "
            "what kind of bike it is and call record_bike first."
        )
    return FunctionResult(...).swml_change_step("schedule")
```

The model may call `start_scheduling` whenever it likes, including on the first
turn. What it cannot do is make the check pass. `SERVICEABLE` is a set in code,
not a line in the prompt, so a caller who insists cannot widen it.

The refusal is prescriptive. It names the state that is missing and the tool
that fills it, so the model's next turn is a question rather than an apology.

One naming trap: `swml_change_step()` is the SDK method, and the key the
platform receives is `change_step`. Assert the key.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/booking/`, using the credentials you set. Without them the request is refused.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and runs the handlers, asserting:

- `identify_bike` exposes two tools and offers the model no `next_step`
- an unserviceable bike is refused and writes no state
- a serviceable one is normalised and written as `set_global_data`
- `start_scheduling` is refused with no state, and refused again when the state
  is present but unserviceable
- with real state it emits `{"change_step": "schedule"}`, and the SDK method
  name appears nowhere in the payload
- `confirm_slot` refuses with no recorded bike, however the call reached it

## Limitations

This governs one transition. A flow with several gates wants the check factored
out, because a rule copied into four handlers is a rule that will disagree with
itself.

Reading `global_data` from `raw_data` trusts the platform's own state, not the
model's account of it. That is the point, but it means the value has to have
been written by a handler.

## What to change first

Delete the `recorded not in SERVICEABLE` check and keep the prompt instruction.
The transition becomes advisory, which is the failure this recipe exists to
prevent.
