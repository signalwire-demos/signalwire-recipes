# Run a Bedrock voice agent

> Swapping `AgentBase` for `BedrockAgent` renders `amazon_bedrock` instead of `ai`, with the prompt carrying three Bedrock settings. The SWAIG function renders with the same schema on both, and the handler you register on each returns the same reply.

**Scenario:** a parts desk you want to run on Amazon Bedrock without rewriting its tools

## What this demonstrates

You swap the base class and the SDK's `agents/bedrock.py` renders the base
document, then rebuilds the verb as `amazon_bedrock`. The `prompt`, `SWAIG`,
`params`, `global_data` and post-prompt settings are copied over. Inside the prompt it
adds `voice_id`, `temperature` and `top_p`; its comment says that in Bedrock
the voice configuration is part of the prompt object. It also drops three
text-model prompt settings if you set them. The bundled schema documents the
verb as `AmazonBedrock`. The `SWAIG.functions` list renders the same on both,
and because one `configure()` registers the tool on each agent, the same
handler runs on both.

## How it works

```python
def configure(agent):
    agent.prompt_add_section("Role", "You are the parts desk at Ridgeline Cycles. ...")
    agent.define_tool(name="check_stock",
                      description="Check whether a bike part is in stock before promising it.",
                      parameters=PARAMETERS, handler=check_stock)
    return agent

def build(kind="bedrock"):
    if kind == "ai":
        return configure(AgentBase(name="parts", route="/parts"))
    return configure(BedrockAgent(name="parts", route="/parts", voice_id="matthew"))
```

What the platform receives, on each base class:

```json
{"ai": {"prompt": {"pom": [...]},
        "SWAIG": {"functions": [{"function": "check_stock", ...}]}}}

{"amazon_bedrock": {"prompt": {"pom": [...], "voice_id": "matthew",
                               "temperature": 0.7, "top_p": 0.9},
                    "SWAIG": {"functions": [{"function": "check_stock", ...}]}}}
```

One `configure()` builds the desk on either class, so there is one place the
prompt and the tool live. `AGENT_KIND` in the environment picks which one
`python app.py` serves, `BEDROCK_VOICE_ID` picks the voice, and any other kind
stops the process with a message.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: the basic-auth pair; AGENT_KIND and BEDROCK_VOICE_ID if you like
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/parts/` and ask about brake pads. Set
`AGENT_KIND=ai` and restart to hear the same desk on the standard model.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier builds the desk on both classes, renders each with the same call
id, and asserts the following.

- the standard document's verbs are `answer`, `ai`; the Bedrock document's are `answer`, `amazon_bedrock`; both validate
- the two `SWAIG.functions` lists are equal once each webhook URL's per-call token is set aside, and each URL points at that agent's `/swaig/` path
- the one function is `check_stock` with `part` required
- the Bedrock prompt's keys are exactly the standard prompt's plus `voice_id`, `temperature` and `top_p`, and every standard key is equal
- the values are the voice the environment set, `tiffany`, and 0.7 and 0.9
- `AGENT_KIND=ai` makes the module's agent render `ai`; an unknown kind stops with a message naming the two choices
- `check_stock` executed on each agent returns the same exact reply for a stocked part, an out-of-stock part and an unknown one
- the bundled schema has an `AmazonBedrock` definition

## Limitations

You prove the documents and the handler. What the Bedrock model does with the
prompt and the voice, and how it sounds, are the platform's side of a live
call. The tool keeps the SDK's `secure` default, so each render carries a
per-call token in its webhook URL; the verifier compares the URLs without it.

`BedrockAgent` drops `barge_confidence`, `presence_penalty` and
`frequency_penalty` from the prompt if you set them; the comment in
`agents/bedrock.py` calls them text-model settings. The verifier sets none, so it does not
exercise that.

## What to change first

Give the Bedrock desk a different tool description in `configure()` by
branching on `isinstance(agent, BedrockAgent)`, and run the verifier. The
functions-equal assertion fails. The recipe's point is that you do not have to
branch.
