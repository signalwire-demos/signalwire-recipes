# Require verification before unlocking AI agent tools

> Account tools do not exist in the model's tool list until a verification tool has succeeded.

**Scenario:** a bank balance line that will not discuss an account until the PIN checks out

## What this demonstrates

The model cannot call a tool that is not active. `get_balance` and
`list_recent_transactions` are declared with `active: false`, so at the start of
the call they are not in the model's world: not discouraged, absent. The only thing that turns them on is a `toggle_functions` action emitted by the
`verify_pin` handler. The handler emits it only when the PIN matches the caller's
record. A prompt that says "verify before discussing the account" is a
request; this is a constraint.

## How it works

```python
@AgentBase.tool(name="get_balance", description="...", parameters={}, active=False)
def get_balance(self, args, raw_data): ...

@AgentBase.tool(name="verify_pin", ...)
def verify_pin(self, args, raw_data):
    if pin_matches(raw_data["caller_id_num"], args["pin"]):
        return (FunctionResult("You are verified.")
                .toggle_functions([{"function": "get_balance", "active": True},
                                   {"function": "list_recent_transactions", "active": True}])
                .toggle_functions([{"function": "verify_pin", "active": False}])
                .update_global_data({"verified": True}))
    return FunctionResult("That PIN does not match.")   # no action: nothing unlocks
```

In the rendered SWML the account functions carry `"active": false`. The
successful handler's reply carries the platform action the model never
composes:

```json
{"toggle_functions": [{"function": "get_balance", "active": true}, {"function": "list_recent_transactions", "active": true}]}
```

The check is code, so a caller from an unknown number with the right digits still
fails, and `verify_pin` retires itself once it has done its job. Retiring is
optional; re-verification mid-call is the same toggle in reverse.

## Run it

```bash
cd python
pip install -r requirements.txt
python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/bank/`, using the credentials from your `.env`. The demo
customer is `+15551234567` with PIN `4242`; replace `CUSTOMERS` with your
system of record.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and asserts the account tools are `active: false`. It then runs
the handler three ways:

- a wrong PIN produces no action
- the right PIN produces a `toggle_functions` action activating exactly the
  account tools
- the right PIN from an unknown number produces no action

## What to change first

Swap the PIN for an OTP: send a code with `send-an-otp-by-sms-with-voice-fallback`
and verify it in the same handler before toggling the tools on.
