# Create a hosted voice AI agent with one REST call

> The `ai` verb your agent renders is what `POST /api/fabric/resources/ai_agents` takes. One POST makes it a resource SignalWire hosts; one more puts a phone number on it. Nothing of yours stays running.

**Scenario:** a shop wants an AI receptionist on its number without running anything of its own

## What this demonstrates

Every agent recipe here serves a document from your host. This one hands the
same definition to the platform instead. `AgentBase` renders the `ai` verb as it
would for a call. Its `prompt`, `params` and `post_prompt` become the body of a
create request, and the response is a resource with an id.

The vendored REST spec, `tools/openapi/rest.json`, is the authority.

- `POST /api/fabric/resources/ai_agents` requires `name` and `prompt`. The spec
  describes `prompt`, `params` and `post_prompt` by pointing at the SWML `ai`
  reference, so the objects the SDK renders are the objects the endpoint wants.
- `POST /api/fabric/resources/{id}/phone_routes` requires `phone_route_id` and
  a `handler`, whose enum is `calling` or `messaging`.
- The number's id comes from `GET /api/relay/rest/phone_numbers` with
  `filter_number`, which is a contains match, so the recipe compares the number
  exactly and refuses one the project does not hold.

A hosted agent has no tool webhooks of yours to call, because there is no host
of yours. This one has none. An agent with tools stays a served agent, or uses
serverless tools. That pattern is
[Let the agent call an API with no server of yours](../call-an-api-without-a-backend/).

## How it works

```python
class FrontDesk(AgentBase):
    def __init__(self):
        super().__init__(name=NAME, route="/front-desk")
        self.prompt_add_section("Role", "You answer the phone for Ridgeline Cycles...")
        self.set_post_prompt("Summarise the call in one sentence.")
        self.set_params({"end_of_speech_timeout": 700})

def definition():
    doc = json.loads(FrontDesk()._render_swml())
    (ai,) = [step["ai"] for step in doc["sections"]["main"] if "ai" in step]
    return {"name": NAME, "prompt": ai["prompt"], "params": ai["params"],
            "post_prompt": ai["post_prompt"]}

client.fabric.ai_agents.create(**definition())
```

What the platform receives, from the Python SDK:

```json
{"name": "ridgeline-front-desk",
 "prompt": {"pom": [{"title": "Role", "body": "You answer the phone for ..."},
                    {"title": "Hours", "body": "Open Monday to Friday, ..."},
                    {"title": "Limits", "body": "You cannot book repairs. ..."}]},
 "params": {"end_of_speech_timeout": 700},
 "post_prompt": {"text": "Summarise the call in one sentence."}}
```

The two SDKs render the same sections in different forms. Python 3.0.1 emits a
`pom` list; `@signalwire/sdk` 2.0.5 emits them as markdown `text` with one
`##` heading per section. The `ai.prompt` schema allows both, and the verifier
validates each as SWML before trusting it as a request body.

The second call is the one every no-server recipe shares:
`client.fabric.resources.assign_phone_route(agent_id, phone_route_id=...,
handler="calling")`.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py create             # prints the resource id
python app.py point <agent_id> +15551230000
```

The TypeScript surface renders its own agent the same way, on Node 20.18.1 or
newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start create
```

The number has to be one the project already holds. Buying it is
[Buy a number and point it at your app](../buy-a-number-and-point-it-at-your-app/).
After the second call, dialling the number reaches the hosted agent, and there
is nothing to keep running.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier renders the agent, swaps the SDK's HTTP layer for a recorder, and
asserts the following.

- the request body is the rendered agent: three sections in order, the post prompt, and the params
- `POST /api/fabric/resources/ai_agents` requires `name` and `prompt`, every key sent is documented, and the spec describes the three objects by pointing at the SWML reference
- the same `prompt`, `params` and `post_prompt`, wrapped back into an `ai` verb, validate against the bundled SWML schema
- the number lookup sends `filter_number`, and with two numbers in the answer the recipe picks the exact match
- the phone route body is exactly `phone_route_id` plus `handler: calling`, and the handler enum is `calling` and `messaging`
- a number the project does not hold raises after the lookup and before any route is posted
- the TypeScript surface renders the same three sections as prompt text, the same params and post prompt, sends the same three requests, and refuses the same number

## Limitations

The verifier proves the requests and the documents, not the call. What the
hosted agent says when the number rings is live behaviour.

A hosted agent cannot call tool webhooks on a host you do not have. Keep tools
serverless, or keep the agent served.

## What to change first

Add `self.define_tool(...)` with a webhook handler to `FrontDesk` and run the
verifier. The rendered `ai` now carries a `SWAIG` object pointing at your host,
and `definition()` drops it. That is the point: the fields this recipe posts are
the ones a hosted agent can honour.
