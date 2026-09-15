# Put an AI agent in a web chat widget

> A page cannot hold a SignalWire API token, so a small gateway on your server holds it. The page learns a publishable key and a signed handle; the gateway injects `config_url`, caps what a leaked key can spend, and forwards each turn to the AI Chat API.

**Scenario:** a talk-to-us box on a shop's site that reaches the same agent as the phone line

## What this demonstrates

[Run the same voice AI agent over text chat](../run-the-same-agent-over-text/)
drives an agent from a server. A web page is not a server: the API token
carries the whole project, and anything in a page is public. This recipe puts
a gateway between the two. The browser sends `POST /chat/` with a publishable
key in `Authorization: Bearer` and a `method` of `start`, `chat`, `log` or
`end`. The gateway does the rest.

- **It injects `config_url`.** The agent's URL lives in the gateway's
  environment and is sent on every `create_conversation`. A `config_url` in
  the page's request is ignored, so a visitor cannot pick which agent runs.
- **It signs the handle.** `start` mints a conversation id and returns
  `<id>.<HMAC>` in an `X-Chat-Handle` header. Every later method carries the
  handle back, and one flipped character is a 403 before any request, so an
  id cannot be forged or guessed.
- **It caps the spend.** New conversations per window and turns per
  conversation are counted in the process, and the platform is not asked once
  a cap is hit. Those two numbers bound what a leaked key can cost, because a
  leaked key opens many one-turn conversations rather than hammering one.
- **It filters the log.** `log` returns `user` and `assistant` entries only,
  never the prompt or the tool traffic.

The wire is modelled on `signalwire.ai_chat.ChatGateway`, which the SDK ships
in releases newer than the pinned 3.0.1, with the same methods, header and
coarse `{"error": reason}` refusals. Its reference is the source for the
design. A publishable key is public by definition. The origin allowlist is
leak containment rather than access control. The caps are what bound the
cost. Upstream, every method is one JSON-RPC 2.0 POST to `/api/ai/chat`, held
to the vendored REST spec.

## How it works

```python
@app.post("/chat/")
def gateway():
    check_key_and_origin()                       # 401, 403; nothing forwarded
    body = request.get_json(silent=True) or {}
    if body.get("method") == "start":
        charge_mint()                            # 429 past MAX_NEW_CONVERSATIONS
        cid, handle = mint_handle()              # "chat-<uuid>.<hmac>"
        made = rpc("create_conversation", {"id": cid, "config_url": CONFIG_URL,
                                           "conversation_timeout": TIMEOUT})
        out = jsonify({"greeting": made.get("initial_message"), ...})
        out.headers["X-Chat-Handle"] = handle
        return out
    cid = read_handle(body.get("handle")) or refuse(403, "handle")
    if body.get("method") == "chat":
        charge_turn(cid)                         # 429 past MAX_TURNS
        return jsonify(rpc("chat", {"id": cid, "message": body["message"]}))
```

What the page sends for a turn, and what the platform receives for it:

```json
{"method": "chat", "handle": "chat-9c41....3f2a...", "message": "When are you open?"}

{"jsonrpc": "2.0", "id": "1f3a...", "method": "chat",
 "params": {"id": "chat-9c41...", "message": "When are you open?"}}
```

The page is `web/widget.html`, served by both surfaces at `/` with the key
substituted in. It calls `start` on load, shows the greeting, and sends each
typed line as a `chat`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env      # token with the chat scope, the agent URL, a key, a secret
python app.py                # the page at http://localhost:8080/
```

`AGENT_CONFIG_URL` is the running agent from the prerequisite recipe, with
its basic-auth pair in the URL. Open the page and type.

The TypeScript surface serves the same page and wire on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Set `ALLOWED_ORIGINS` to the site that will embed the page before deploying;
localhost is always allowed so development works unconfigured.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the Flask app with its test client, swaps the SDK's HTTP
layer for a recorder, and asserts the following.

- the page carries the key and neither the token, the secret nor the agent URL
- a request without the key is a 401, one from a foreign origin a 403, a local origin is allowed, and none of the refusals reach the platform
- `start` sends `create_conversation` with the handle's id, the configured `config_url` and the timeout, every param documented and every required one present, and answers with the greeting and an `X-Chat-Handle` header
- a handle with one flipped character, or another id under a valid signature, is a 403 with no request
- a turn forwards the message under the handle's id and drops a `role` and a `config_url` the page tried to send; an empty message is a 400
- the third turn on a two-turn cap and the third `start` on a two-conversation cap are 429s with no request
- `log` returns user and assistant entries only, `end` sends `end_conversation`, and an unknown method is a 400
- the token appears in no response body or header
- a JSON-RPC error from the service is a JSON 502 the page can show, not an HTML 500
- a body past 16 KiB is a 413 with no request, and in Node the key is checked before a byte of it is buffered
- a turn counter left by a visitor who never sent `end` is forgotten after the conversation timeout, and a live one is kept
- a cap that does not parse stops the Node process instead of disabling itself
- the page's form is disabled until `start` answers and while a turn is out
- the TypeScript surface, on a real port, serves the same page, refuses the same requests, caps the same counts and sends the same six envelopes

## Limitations

The counters live in the serving process. Behind several replicas each keeps
its own, so the effective cap multiplies by the replica count. Put a shared
limiter in front, or accept that.

The origin allowlist stops a key pasted into someone else's page. It does not
stop `curl`, which omits the header. The caps are what bound that.

A page refresh loses the handle, so the visitor starts a new conversation.
Keeping it in `sessionStorage` is a page change, not a gateway change. The
`end` sent on `pagehide` is best effort; the turn counter expires on its own
if it never arrives.

The verifier proves the gateway and the envelopes, not the model's replies.

## What to change first

Remove `charge_turn(cid)` from the `chat` branch and run the verifier. The
third turn now reaches the platform and the cap assertion fails. That is the
point: without it a leaked key spends without limit.
