# Remember a returning caller across calls

> Two `ai.params` carry memory between calls. `save_conversation` makes the platform post a summary when a call ends, and `conversation_id` names the conversation it belongs to. Name it after the caller and the next call can ask for it back.

**Scenario:** a customer who called yesterday about a tune-up calls back and the agent already knows

## What this demonstrates

An agent forgets everything when the call ends unless something keeps it. The
platform offers to: `save_conversation` posts a summary to your
`post_prompt_url` at the end of the call, and `conversation_id` says which
conversation that summary belongs to. This recipe derives the id from the
caller's number, keeps each summary in a file, and answers the platform's
request for it on the next call.

Three sources carry the claim.

- The docs for `ai.params` say `save_conversation` will "send a summary of the
  conversation after the call ends", that it requires `post_prompt_url` and a
  `conversation_id`, and that `conversation_id` is "used by `check_for_input`
  and `save_conversation` to identify an individual conversation".
- The inbound-call payload the platform POSTs for a SWML document carries
  `call.from`, so the per-request callback can set both params before the
  document renders.
- The SDK's own post-prompt route handles the return trip. In 3.0.1 it calls
  `on_summary(summary, body)`. When the body's `action` is `fetch_conversation`
  it returns whatever `on_summary` returned. Its comment says the platform
  "expects `conversation_summary` in the response" (`core/mixins/web_mixin.py`).

The Python surface uses that route as it is. The TypeScript SDK, 2.0.5, answers
every post-prompt POST with `{ok: true}` and drops `onSummary`'s return. Its
surface therefore points `post_prompt_url` at a small handler of its own, which
is what `setPostPromptUrl` is for.

## How it works

```python
def configure(query_params, body_params, headers, agent):
    caller = (body_params.get("call") or {}).get("from")
    if caller:
        agent.set_params({"save_conversation": True,
                          "conversation_id": conversation_id(caller)})

class FrontDesk(AgentBase):
    def on_summary(self, summary, raw_data=None):
        cid = raw_data.get("conversation_id")
        if raw_data.get("action") == "fetch_conversation":
            remembered = _load().get(cid)
            return {"conversation_summary": remembered} if remembered else {}
        if summary and cid:
            memory = _load(); memory[cid] = summary; _save(memory)
```

What the document carries for a call from +1 415 555 0123:

```json
{"ai": {"params": {"save_conversation": true, "conversation_id": "caller-14155550123"},
        "post_prompt": {"text": "Summarise the call in two sentences, ..."},
        "post_prompt_url": "https://your-host/front-desk/post_prompt"}}
```

The callback runs against an ephemeral copy of the agent on every request. One
caller's id never leaks into another caller's document, and a request with no
caller renders no id at all. The id is the caller's digits, which keeps it
inside the characters the SDK accepts for a conversation id.

A `post_prompt` is set because in 3.0.1 that is what makes the SDK emit
`post_prompt_url`. The summary it asks for is also the text that gets kept.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, basic auth
python app.py                    # serves /front-desk/ and /front-desk/post_prompt
```

The TypeScript surface serves the agent on one port and its post-prompt handler
on another, on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
POST_PROMPT_URL=https://your-host/post_prompt npm start
```

The code adds the basic auth credentials from `.env` to that URL. The platform
gets only the URL, and the handler checks them.

Point a number at `https://your-host/front-desk/` behind the basic auth in
`.env`. Call it, say something worth remembering, hang up. Call again from
the same number.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the agent's real app with `TestClient` and asserts the
following.

- a SWML request whose body carries `call.from` renders `save_conversation: true`, a `conversation_id` built from that number, a `post_prompt`, and a `post_prompt_url` ending in the post-prompt route, and the document validates
- a second caller renders a second id, and a request with no caller renders none
- a `post_conversation` POST for each caller returns `{"success": true}` and both summaries are in the file
- after a module reload, `fetch_conversation` for the first caller returns `{"conversation_summary": ...}` with that caller's text, an unknown id returns `{}`, and the file is unchanged
- an unauthenticated fetch is a 401
- the TypeScript surface renders the same two params per caller, points `post_prompt_url` at its own handler, and that handler saves, answers the fetch, returns `{}` for an unknown id, and refuses a request without credentials

## Limitations

A caller whose number carries no digits, an anonymous call or a SIP URI
without any, gets no conversation id. Nothing is saved or fetched for them.
One memory shared by every anonymous caller would hand one caller's summary to
the next.

The verifier proves the document and the two POSTs, not what the model does
with the summary on the next call. That is the prompt's job, and the *Memory*
section is where it is asked.

The exact shape of the platform's fetch request is documented in the SDK's
route rather than in a spec. The recipe reads `action` and `conversation_id`
from the body, as the route does.

## What to change first

Remove `"save_conversation": True` from `configure` and run the verifier. The
document still carries the id and the post prompt, and the first assertion
fails. That is the point: without that flag nothing is saved, and the next call
has nothing to fetch.
