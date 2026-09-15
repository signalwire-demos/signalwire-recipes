# Run the same voice AI agent over text chat

> The agent your phone number reaches is reachable over text, with no second definition. `POST /api/ai/chat` takes a JSON-RPC body whose `config_url` is the URL the agent already serves its SWML from. One request is one turn.

**Scenario:** a bike shop's phone receptionist answers the same questions in a support chat

## What this demonstrates

An `AgentBase` serves a SWML document at its route, and a phone number fetches
that document when a call arrives. The AI Chat API fetches the same document.
You name a conversation and hand the platform the agent's URL as `config_url`.
Each `chat` request then runs one turn: the user's message, the agent's reply,
and any tool calls made along the way. The prompt, the tools and the post prompt
are the ones the voice channel uses, because they are the same object.

The vendored REST spec, `tools/openapi/rest.json`, is the authority.

- Six methods travel over the one endpoint in a JSON-RPC 2.0 envelope:
  `create_conversation`, `chat`, `end_conversation`, `delete`, `chat_log` and
  `summarize`. The envelope requires `jsonrpc`, `id`, `method` and `params`.
- `create_conversation` requires the conversation `id` and `config_url`, "the
  publicly reachable URL serving your agent's SWML"; `localhost` and private
  addresses cannot be fetched. Its result carries `initial_message` when the
  agent greets first.
- `chat` requires `id` and `message`. Its `role` is `user` or `system`, and
  "a `system` message steers the agent without appearing as something the
  user said". The result is `response`, plus a `user_event` when a tool raised
  one.
- `end_conversation` runs post-processing, which is where the post prompt
  fires; `delete` removes the conversation without it.
- The token needs the `chat` scope, and a JSON-RPC error arrives inside an
  HTTP 200, so the HTTP layer does not raise for it.

Later SDK releases wrap this wire as `signalwire.ai_chat.AIChatClient`. The
pinned 3.0.1 does not, so the recipe sends the envelopes through
`RestClient`'s HTTP layer, the way the redact and SIP-address recipes do.

## How it works

```python
class FrontDesk(AgentBase):            # the agent a phone call reaches
    def __init__(self):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", "You answer for Ridgeline Cycles...")
        self.set_post_prompt("Summarise the conversation in one sentence.")

channel = TextChannel()                # six methods over client._http
made = channel.create(cid, config_url(agent))
print(made["initial_message"])
print(channel.say(cid, "When are you open?")["response"])
channel.end(cid)
```

What the platform receives for the first turn:

```json
{"jsonrpc": "2.0", "id": "1f3a...", "method": "chat",
 "params": {"id": "text-9c41...", "message": "When are you open?"}}
```

`config_url` is the agent's route with the trailing slash the SDK registers,
on your public host, carrying the basic-auth pair from `.env`. The platform
gets only the URL, so the credentials travel inside it, the same way the SDK
builds its own webhook URLs.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, token with the chat scope, basic auth
python app.py serve              # the agent at /front-desk/
```

Expose the agent with a tunnel, set `AGENT_PUBLIC_URL` in `.env` to that
host, and in a second terminal:

```bash
python app.py chat               # type; 'bye' summarises and ends
```

The TypeScript surface does the same on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start serve                  # and, in another terminal, npm start chat
```

Point a number at the same URL and the phone reaches the same agent.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier drives the agent's real app with `TestClient`, swaps the SDK's
HTTP layer for a recorder, and asserts the following.

- the app serves a document that validates, behind basic auth from the environment, and an unauthenticated request is a 401
- the config URL is the agent's route with a trailing slash on the public host, carrying the basic-auth pair
- create, two chats, `chat_log`, `summarize`, `end_conversation` and `delete` each POST the documented path as a JSON-RPC 2.0 envelope with a unique request id
- for every method the params carry the spec's required fields and nothing the spec does not document, and the `role` enum is read from the spec
- a role outside the enum is refused before any request is sent
- an error envelope inside a 200 raises with its code, and a summary failure riding the success envelope raises rather than returning an empty string
- the TypeScript surface serves the same document, builds the same URL, sends the same seven envelopes and refuses the same role

## Limitations

The verifier proves the envelopes and the document, not the model's replies.
What the agent says in a turn is live behaviour.

The agent has no tools here, so a turn is one model round trip. A tool webhook
is fetched from your host during the turn, like a call; the URL has to be
public for that too.

The service limits one request to 30 seconds and answers a slower turn with a
502, per the SDK's client reference. A turn is measured in seconds.

## What to change first

Add a tool to `FrontDesk` with `define_tool` and run the verifier. The
document still validates and the envelopes do not change, because the tool
belongs to the agent and not to the channel. Then send a question the tool
answers and read the turn's `user_event`.
