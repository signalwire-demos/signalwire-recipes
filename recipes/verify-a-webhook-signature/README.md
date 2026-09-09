# Verify a webhook signature

> The gate refuses, with 403 and before any route runs, a request whose signature header does not match hex(HMAC(signing_key, url + raw_body)). `X-Signalwire-SHA256-Signature` decides when present; otherwise `X-Signalwire-Signature`, the SHA-1 one, does.

**Scenario:** a public webhook that refuses any request without a valid SignalWire signature

## What this demonstrates

SignalWire signs the requests it makes to your webhooks. The SWML webhook
security guide documents two headers. `X-Signalwire-Signature` is "HMAC-SHA1,
hex encoded" and arrives on every signed request. `X-Signalwire-SHA256-Signature`
is "HMAC-SHA256, hex encoded" and arrives on call requests. The signed payload
is "the request URL concatenated directly with the raw request body, with no
separator", so the formula is `hex(HMAC(signing_key, url + raw_body))`. You
find the key in the Dashboard under API Credentials, as Signing Key
(https://signalwire.com/docs/swml/guides/webhook-security).

The check runs in a Flask `before_request` hook, so it runs before routing. A
request that fails it never reaches a route handler, not even a 404.

## How it works

```python
def expected(key, url, raw_body, digest):
    return hmac.new(key.encode(), url.encode() + raw_body, digest).hexdigest()

def verify(headers, url, raw_body, key=None):
    key = key or SIGNING_KEY
    for header, digest in DIGESTS.items():          # SHA-256 first, then SHA-1
        if header in headers:                       # presence selects the digest
            sent = headers[header]
            if not HEX.fullmatch(sent):             # not hex: refuse, do not compare
                return False
            return hmac.compare_digest(sent, expected(key, url, raw_body, digest))
    return False

@app.before_request
def gate():
    url = WEBHOOK_URL + ("?" + request.query_string.decode() if request.query_string else "")
    if not verify(request.headers, url, request.get_data()):
        abort(403)
```

Two choices matter. The URL comes from `WEBHOOK_URL`, the address you gave
SignalWire, not from the request. A tunnel or a proxy can present Flask with a
different host, and the platform signed the one you configured. The guide says
the URL includes the query string, so the hook appends the request's. And
`hmac.compare_digest` is the comparison Python's `hmac` documentation describes
as "designed to prevent timing analysis". When both headers arrive, presence of
the SHA-256 header selects it. An empty or wrong SHA-256 then fails rather than
falling back to SHA-1.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: SIGNALWIRE_SIGNING_KEY and WEBHOOK_URL
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok, and set `WEBHOOK_URL` to `https://<your-host>/webhook`,
with no query string; the gate appends each request's own. Point a number's
SWML webhook at that URL and call it. Then send the same URL a `curl` with no header and read the
403.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier drives the Flask app with its test client and a signing key of its
own. It asserts the following.

- a body signed with SHA-1 over `url + body` is served, and the reply is a SWML document that validates with `answer`, `play`, `hangup`
- a body signed with SHA-256 alone is served
- when both headers arrive the SHA-256 one decides: a valid SHA-1 beside a wrong or empty SHA-256 is refused
- no header, a body altered by one byte, and a signature from another key are each refused with 403
- the gate refuses a signature over `url + "\n" + body`, a wrong SHA-256, an empty header, and a header that is not hex, each with 403
- the same valid signed request, sent twice, is served twice: the gate does not stop a replay
- a request with a query string is served only when the signature covers the query string
- an unknown path is 403, not 404, because the gate runs before routing, and a signature valid for the webhook URL replayed at another path is 403 too
- a `WEBHOOK_URL` configured with a query string is refused at startup, in a fresh interpreter
- `verify()` on its own agrees with the app, so you can call it outside Flask

## Limitations

The verifier signs with its own key, so it proves the arithmetic and the gate,
not that a given production request came from SignalWire. That proof is the
signature on your real traffic against your real key.

The check is an HMAC over the URL and body, so it says the sender held the
key and the body is unchanged. It says nothing about when the request was
made: the verifier sends one valid request twice and the gate serves both. Add
your own check against replay, such as refusing a `call_id` you have already
served.

The guide says the URL "excludes basic auth credentials on call requests" and
includes them on messaging requests "as configured". Set `WEBHOOK_URL` to match
the kind of webhook you serve.

## What to change first

Change the separator: sign over `url + "\n" + raw_body` in `expected()` and run
the verifier. Every served request becomes a 403 and the "a separator" case is
served instead. The formula is the platform's, not yours.
