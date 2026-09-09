# Inject a message into a live AI call

> One REST command, `calling.ai_message`, addresses a running call by id. Its params carry a system message, a `global_data` merge, or a reset with a new system prompt.

**Scenario:** your CRM finishes a lookup after the call started and tells the agent who is on the line

## What this demonstrates

`POST /api/calling/calls` with `command: calling.ai_message` addresses a call
that is running an AI agent, by id. The body carries the call `id` at the top level and
a `params` object. The vendored REST spec, `tools/openapi/rest.json`, describes
the `system` role as injecting "instructions or context that modify the AI's
behavior mid-conversation without the caller hearing it". The same params take
`global_data`, "arbitrary JSON data to merge into the AI session's global data
store", or `reset`, with `full_reset` and a new `system_prompt`.

The verifier proves the request. The spec is the authority for what the
platform does with it.

## How it works

```python
client = RestClient()

def nudge(call_id, instruction):
    return client.calling.ai_message(call_id, role="system", message_text=instruction)

def share(call_id, data):
    return client.calling.ai_message(call_id, global_data=data)

def restart(call_id, system_prompt):
    return client.calling.ai_message(
        call_id, reset={"full_reset": True, "system_prompt": system_prompt})
```

What the platform receives for `nudge`:

```json
{"command": "calling.ai_message",
 "id": "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f",
 "params": {"role": "system",
            "message_text": "The caller is a returning customer. Skip the identity questions."}}
```

The SDK's `calling` namespace, `rest/namespaces/calling.py`, sends every call
command to that one path. It puts the call id in `id`. The spec marks
`command`, `id` and `params` required for this command. Its `role` enum is
`system`, `user` or `assistant`. The spec describes `user` as "a message as if
the caller said it" and `assistant` as "a message as if the AI said it".

Your backend learns the call id from the agent. The tool webhook body carries
it as `call_id`; see the
[SWAIG tool webhook](https://signalwire.com/docs/apis/rest/webhooks/ai-swaig-tool-webhook).

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py <call_id> "The caller is a returning customer."
```

Take the call id from a tool webhook of a call that is running an AI agent.
There is no server to expose; the script speaks to the REST API and exits.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, calls the three helpers,
and asserts the following.

- each helper adds exactly one `POST` to the documented calling path
- the spec marks `command`, `id` and `params` required for this command, and the observed role is in its enum
- each body equals `{"command": "calling.ai_message", "id": <call id>, "params": ...}` with the exact params
- every param is a documented property of the spec's variant, and so is every key nested under `reset`

## Limitations

The verifier proves the request, not the model's reaction. What the next turn
does with a system message is the model's behaviour on a live call.

The spec describes a `user` role message as one the AI treats "as if the caller
said it". Keep it out of flows where the caller's words matter as a record.

## What to change first

Change `role="system"` to `role="operator"` in `nudge` and run the verifier.
The role assertion fails, which is the point: the three roles are the whole
vocabulary.
