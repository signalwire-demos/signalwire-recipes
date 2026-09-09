# Protect AI agent tool webhooks with per-call tokens

> Every tool webhook request must carry a token minted for that call and that function. The endpoint refuses anything else before a handler runs.

**Scenario:** an account line where a refund must not be triggered from outside the call that asked

## What this demonstrates

Every tool renders its `web_hook_url` with a `__token` query parameter minted for
this call and this function. The endpoint refuses a token from another call, for
another function, altered, or expired, and the handler does not run. The two
tools in this recipe never set `secure`; the tokens are the default.

The SDK checks a token only when one is present. A request that omits it, or sends
an empty one, is not refused by the token layer. The basic-auth credentials that
gate the route sit in the same URL an attacker captured, so they do not close that
gap either. This agent adds one rule of its own: no token, no handler.

## How it works

You write nothing to get the tokens. The document rendered for a call carries,
per function:

```json
{"function": "issue_refund",
 "web_hook_url": "https://user:pass@host/accounts/swaig/?__token=Y2FsbC1BLmlz..."}
```

The SDK's `SessionManager` (`signalwire/core/security/session_manager.py`) mints
the token. It is an HMAC over the call id, the function name, an expiry and a
nonce, signed with a key generated when the process starts. Its `validate_token` checks
the function name, then the expiry, then recomputes the signature, then compares
the call id. Any mismatch returns a refusal in the function result, and the
handler does not run.

The rule you add sits on the app the SDK builds:

```python
app = agent.get_app()

@app.middleware("http")
async def require_token(request, call_next):
    if request.url.path.rstrip("/") == tool_path and request.method == "POST":
        if not request.query_params.get("__token"):
            return JSONResponse(status_code=403,
                                content={"response": "A per-call token is required."})
    return await call_next(request)
```

The test is `not ...get("__token")`, not a key check. A request with `?__token=`
has the key, and the SDK treats the empty value as no token at all. In the SDK,
`serve()` runs the app that `get_app()` built and cached, so the middleware sits
in front of every tool request. `token_expiry_secs` on the constructor sizes the
window: the SDK default is 3600 seconds, and this recipe sets 900 through
`TOKEN_TTL_SECONDS`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/accounts/`.

## Verify it

No network, no account. The verifier drives the agent's own HTTP app with
FastAPI's test client, the way the platform would, and records every handler run.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the document for one call, takes the refund tool's token off its URL,
and POSTs to the tool endpoint, asserting the following.

- both tools, which never set `secure`, render with distinct tokens
- without basic auth the route answers 401 and nothing runs
- each tool's token, on its own call and function, runs that handler once and returns its text
- a token on another call, on the other function, or with a character changed gets the SDK's refusal and runs nothing, in both directions
- a token minted with a closed expiry window gets the same refusal
- a request with no token, and one with an empty token, each get a 403 from the middleware and run nothing

The verifier never prints a URL, because the URLs carry your basic-auth credentials.

## Limitations

The middleware is the recipe's rule, not the SDK's. Without it, a request with no
token reaches the handler as soon as it passes basic auth.

Your process generates the signing key at start. `AgentBase.__init__` builds the
`SessionManager` with only `token_expiry_secs`, so there is no constructor
argument to share a key. Two replicas behind a load balancer will each refuse the
other's tokens.

## What to change first

Delete the `require_token` middleware and run the verifier. The last check fails:
a request with no token now runs `issue_refund`, which is the gap this recipe
exists to close.
