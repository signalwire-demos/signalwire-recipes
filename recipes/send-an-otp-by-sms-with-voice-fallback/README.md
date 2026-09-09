# Send an OTP by SMS, with voice fallback

> The MFA API sends a code by SMS, re-sends it by voice call if asked, and verifies it; you store no codes.

**Scenario:** two-factor login for a web app whose users may not receive SMS

## What this demonstrates

One-time codes are a platform service, not something you generate, store,
expire and rate-limit yourself. `POST /mfa/sms` creates and delivers a code, returning a request id. If SMS does not
arrive, or the user is on a landline, `POST /mfa/call` reads the code out on a phone
call instead. `POST /mfa/{id}/verify` checks what the user typed. Your application holds only
the request id.

## How it works

```python
client.mfa.sms(to=to, **{"from": FROM}, message="Your verification code is: ",
               token_length=6, valid_for=300, max_attempts=3, allow_alphas=False)   # -> {"id": ...}
client.mfa.call(...)                                                                   # same parameters, by voice
client.mfa.verify(request_id, token=token)                                             # -> {"success": true|false}
```

Expiry (`valid_for`, seconds) and the attempt cap (`max_attempts`) are enforced
by the platform. The Flask routes are the thinnest possible wrapper so the
three calls are visible; in a real app the request id lives in the session.

This is a different thing from `require-verification-before-unlocking-tools`:
that recipe gates an AI agent's tools on a check; this one is the check.

## Run it

```bash
cd python
pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... SIGNALWIRE_PHONE_NUMBER=+1555...
python app.py
curl -X POST localhost:8080/otp/start  -H 'content-type: application/json' -d '{"to": "+1555..."}'
curl -X POST localhost:8080/otp/verify -H 'content-type: application/json' -d '{"request_id": "...", "token": "123456"}'
```

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, the verifier checks the three documented MFA requests
and their required bodies against `tools/openapi/rest.json`. It also confirms that the
voice fallback carries the same parameters as the SMS send, and that the application
generates no codes of its own.

## What to change first

Use the verified request id to unlock an agent's tools
(`require-verification-before-unlocking-tools`) or to trust a caller ID in
`buy-a-number-and-point-it-at-your-app`'s tenant onboarding.
