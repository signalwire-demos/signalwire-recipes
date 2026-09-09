# Check consent before an outbound call

> You place an outbound call only when the number has affirmative consent on record. The current time must also be inside the permitted window in the callee's time zone. The check is code, and it runs before the `dial`, so a refused call is never a request.

**Scenario:** a workshop that calls customers when their bikes are ready, and only the ones who asked

## What this demonstrates

The platform's part is one `dial` on `POST /api/calling/calls`. The recipe is
the ordering around it. `place()` looks the number up in your consent store and
converts the current time to the callee's zone with `zoneinfo`. It checks that
time against a window. Each failed consent or window check raises `NoConsent`
with the reason before the code reaches `client.calling.dial`. A clock with no
time zone raises `ValueError` instead. The verifier records no HTTP request for
a refused call, because the code never builds one.

## How it works

```python
def allowed(number, now=None):
    if now is not None and now.utcoffset() is None:
        raise ValueError("now must carry a time zone")
    record = CONSENT.get(number)
    if not record:
        return "no consent on record"
    if not record["consented"]:
        return "consent withdrawn"
    local = (now or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(record["tz"]))
    if not WINDOW[0] <= local.time() <= WINDOW[1]:
        return f"outside the calling window, it is {local:%H:%M} in {record['tz']}"
    return None

def place(number, message, now=None):
    reason = allowed(number, now)
    if reason:
        raise NoConsent(f"not calling {number}: {reason}")
    return client.calling.dial(**{"from": FROM, "to": number, "timeout": 25, "swml": ...})
```

What the platform receives, after every check passes:

```json
{"command": "dial",
 "params": {"from": "+15550001111", "to": "+15557654321", "timeout": 25,
            "swml": {"version": "1.0.0", "sections": {"main": [
              {"answer": {}}, {"play": {"url": "say:Your bike is ready."}}, {"hangup": {}}]}}}}
```

The code judges the window in the callee's zone, which is part of the consent
record. It refuses a callee in Los Angeles at 21:30 even when the server clock
reads 04:30 tomorrow. It allows one at 19:00 when the server reads 02:00.
`CONSENT` here is a dictionary. With counsel, decide which consent details your
production store must retain.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token, space and number
python app.py +1XXXXXXXXXX       # the destination you added to CONSENT
```

Before the first run, add the destination you have consent to call to
`CONSENT` in `app.py`. Give it `consented` set to `True` and its time zone, then pass
that same number. There is no server to expose; the script speaks to the REST
API and exits. For a refused number `place()` raises `NoConsent` with the
reason.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, fixes the clock, and
asserts the following.

- a number with no record raises `NoConsent` saying so, and the recorder sees no request
- a number that withdrew consent does the same
- a consented number at 21:30 local time raises `NoConsent` naming the window and `21:30`
- the window is the callee's: 02:00 UTC is outside a 09:00 to 20:00 window, and the same instant is 19:00 in Los Angeles and passes
- the window is closed at both ends: 09:00 and 20:00 local pass, 08:59 and 20:01 raise, with no request for either refusal
- with no `now` supplied, the code reads the clock itself: a frozen clock inside the window dials, one outside raises
- a clock with no time zone raises `ValueError` rather than passing in the server's zone
- the consented number in the window makes exactly one `POST` to the documented calling path
- the body equals one expected object: `command: dial` and params of `from`, `to`, `timeout`, and the inline SWML with its three verbs in order
- those params are documented properties of the SWML dial variant, the required ones are present, and the inline SWML validates

## Limitations

This is the ordering, not the law. Which hours count, what consent must say,
and how long a record is good for are yours to decide with counsel, and vary by
jurisdiction.

The store is in memory. `handle-opt-outs-yourself` handles the messaging
opt-out with a record of its own.

## What to change first

Change `WINDOW` to `(time(9, 0), time(22, 0))` and run the verifier. The
21:30 refusal no longer happens and that assertion fails. The window is a value
you set, and the verifier pins the one this recipe chose.
