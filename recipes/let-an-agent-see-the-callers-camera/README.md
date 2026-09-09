# Let a voice AI agent see the caller's camera

> `enable_vision: true` in `ai.params` turns on the platform's `get_visual_input` function for the agent. `vision_model` names the model, and an internal filler under `get_visual_input` gives the agent something to say for it.

**Scenario:** a workshop desk on a video call that wants to see the worn part before it gives advice

## What this demonstrates

The bundled schema documents `enable_vision` as "Enables visual input
processing for the AI Agent. When set to `true`, the AI Agent will be able to
utilize visual processing capabilities, while leveraging the `get_visual_input`
function". Its default is false. `vision_model` names the model. The schema
says "Allowed values are `gpt-4o-mini`, `gpt-4.1-mini`, and `gpt-4.1-nano`",
and its type also admits any other string.
You do not define `get_visual_input`. The schema lists it among the internal
fillers, not among the functions you register, and not among the native
functions you can switch on. What you can give it is a filler, a phrase filed
under its name.

## How it works

```python
class EyesAgent(AgentBase):
    def __init__(self):
        super().__init__(name="eyes", route="/eyes")
        self.prompt_add_section("Role", "You are the workshop desk at Ridgeline Cycles, on a video call. ...")
        self.set_params({"enable_vision": True, "vision_model": VISION_MODEL})
        self.set_internal_fillers({"get_visual_input": {"en-US": LOOKING}})
```

What the platform receives, inside the `ai` verb:

```json
"params": {"enable_vision": true, "vision_model": "gpt-4o-mini"},
"SWAIG": {"internal_fillers": {"get_visual_input": {"en-US": ["Let me take a look.",
                                                              "One moment while I look at that."]}}}
```

The prompt tells the agent to look before it answers and to describe what it
sees. The SDK warns at registration if you name a filler the schema does not
know, which is the check that keeps `get_visual_input` spelt right.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: the basic-auth pair; VISION_MODEL if you like
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a video-capable client or
Fabric address at `https://<user>:<password>@<your-host>/eyes/`, hold a part
up to the camera and ask about it.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier renders the agent's document, validates it, and asserts the
following.

- `ai.params` carries `enable_vision: true` and the `vision_model` the environment set, `gpt-4.1-nano`, which is not the app's default
- `SWAIG.internal_fillers` is exactly `get_visual_input` with the two phrases, and no function named `get_visual_input` is registered
- the prompt tells the agent to look before it answers and to describe what it sees
- the schema's `enable_vision` description names `get_visual_input` and its default is false
- the schema's `vision_model` is exactly three named values plus any string
- the schema lists `get_visual_input` among the internal fillers and not among the native functions

## Limitations

You prove the document and the schema. When the agent looks, what the model
sees, and how it describes it are the platform's side of a live video call.

The schema names three models and admits any string; which one to use is a
quality and cost decision this recipe does not make for you.

## What to change first

Change `VISION_MODEL` in `.env` to `gpt-4.1-mini` and run the agent. The
document renders with that model in `ai.params`, because the environment is
where the name comes from. The verifier sets `gpt-4.1-nano` for the same
reason, and fails if the app ignores the variable.
