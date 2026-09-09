# Give a voice AI agent a tool

> Let the model call your function, and decide what it gets back.

**Scenario:** an order status line for a home goods retailer

## What this demonstrates

A decorated Python function, or a `defineTool` call in TypeScript, becomes something
the model can call mid-call. You declare the arguments as JSON Schema. The SDK renders the function into the tool schema the
model already understands, and your handler runs when it is called. The model asks;
your code answers.

A SWAIG function is not a different thing from an LLM tool. The document holds a SWAIG
definition, and the platform renders it into the tool schema the model reads on every
turn.

## How it works

`@AgentBase.tool` takes the name the model emits, the description it reads, and
`parameters` as a JSON Schema dict. There is no `AgentBase.parameter()` helper.

```python
@AgentBase.tool(
    name="get_order_status",
    description="Look up the delivery status of a customer's order by its "
                "order number. Use this BEFORE stating any status or date.",
    parameters={"type": "object",
                "properties": {"order_id": {"type": "string",
                                            "description": "Exactly five digits."}},
                "required": ["order_id"]},
    fillers={"en-US": ["Let me pull that order up."]},
)
def get_order_status(self, args, raw_data):
    ...
```

Both description fields are prompt engineering, not developer documentation.
The model reads them to decide when to call the tool and how to fill the
argument. A vague description is the usual reason a model has the right tool and
never calls it.

The handler returns a `FunctionResult`, never a raw string. On a miss it returns
a typed state, `NOT_FOUND`, with an instruction for what to do next. Without
that, an unanswered lookup invites the model to fill the silence with a delivery
date it invented.

The spoken sentence is built in the handler. Formatting for voice belongs in the
return value, not in a prompt bullet asking the model to say it nicely.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/orders/`, using the credentials you set. Without them the request is refused.

The TypeScript surface is the same agent with `defineTool` on `@signalwire/sdk`, on Node 20.18.1
or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start            # serves /orders/ and /orders/swaig
```

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and asserts:

- `get_order_status` appears in `ai.SWAIG.functions` with `order_id` required
- the function and its parameter both carry a description the model can act on
- the fillers reach the platform
- a known order returns the status, date and carrier as one spoken sentence
- an unknown order returns `NOT_FOUND` and no date from any real order
- the TypeScript surface renders the same function definition, and its own `/swaig` route, posted the documented `argument` shape, returns the same two sentences and refuses a request without credentials

## Limitations

The SDK puts tool-selection accuracy as degrading past roughly seven or eight
simultaneously active tools (`core/mixins/tool_mixin.py`). When an agent grows past
that, scope them per step rather than adding another (`scope-tools-per-step`).

`secure=True` is the default, so the callback requires a SWAIG token. Leave it
on for anything touching a real customer record.

The platform posts a tool's arguments as `argument: {parsed: [args], raw}`, the
documented SWAIG tool webhook. The TypeScript SDK's `/swaig` route in 2.0.5
hands `argument` to the handler as posted, so a handler reading `order_id`
would find `parsed` and `raw` instead. The surface overrides `onFunctionCall`
to unwrap the documented shape before dispatch, and the verifier posts that
shape. Remove the override and the known order comes back `NOT_FOUND`.

## What to change first

Replace the description with "Lookup function" and call the agent. The tool is
still there and the model stops choosing it.
