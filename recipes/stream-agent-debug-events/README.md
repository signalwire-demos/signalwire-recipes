# Stream voice AI agent debug events

> Two `params` on the `ai` verb make the platform POST each debug event the level selects to your endpoint as it happens. The SDK routes every one to a handler you register.

**Scenario:** a message-taking agent whose barges and model errors you want to see live

## What this demonstrates

`enable_debug_events(level)` writes `debug_webhook_url` and `debug_webhook_level`
into the document's `params`. The URL is the agent's own `/debug_events` route,
behind the same basic auth as the rest of the agent. The platform POSTs each
event the level selects, and the function you register with `on_debug_event`
receives every one with its label and full body.

The [ai params reference](https://signalwire.com/docs/swml/reference/ai/params)
documents both fields. `debug_webhook_url` receives "each interaction between
the AI and end user". `debug_webhook_level` is `0` to `2`, and level 2 adds
`conversation_add`, `llm_request` and `llm_response`.

## How it works

```python
class WatchedAgent(AgentBase):
    def __init__(self):
        super().__init__(name="watched", route="/watched")
        self.enable_debug_events(level=DEBUG_LEVEL)

@agent.on_debug_event
def watch(event_type, data):
    EVENTS.append((event_type, data.get("call_id")))
    if event_type == "llm_error":
        ERROR_EVENTS.append({"call_id": data.get("call_id"), "detail": data})
```

What the platform receives in the document:

```json
{"params": {"debug_webhook_url": "https://user:pass@host/watched/debug_events/?__token=...",
            "debug_webhook_level": 1}}
```

The SDK's route, `_handle_debug_events_request` in `web_mixin.py`, reads the
event label from `label` and falls back to `action`. It logs the event as
`debug_event`, then calls your handler with the label and the whole body,
awaiting it if it is async. The `enable_debug_events` docstring in
`ai_config_mixin.py` describes level 1 as barge, errors, session start and end,
and step changes.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/watched/`, call, and interrupt the agent
mid-sentence. The `debug_event` log line names the event.

## Verify it

No network, no account. The verifier drives the agent's own HTTP app with
FastAPI's test client and POSTs events in the documented shape.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders and validates the SWML, then asserts the following.

- `params.debug_webhook_url` points at this agent's `/debug_events` route and `debug_webhook_level` is 1
- with `DEBUG_LEVEL=2` the document says 2
- the route refuses a POST without basic auth and does not call the handler
- the route refuses a GET with 405
- a `barge` POST returns `{"status": "ok"}` and the handler receives `("barge", call_id)`
- an `llm_error` POST reaches the handler, which records the body on its own list
- a body with `action` but no `label` reaches the handler under the action name
- the plain-SWML surface validates with the same two params

## Limitations

The verifier posts events of the documented shape; it cannot generate the
platform's own. Which labels arrive at level 1 is the SDK's description, not
something proven here.

Level 2 posts every model request and response. Through a tunnel on one call
that is fine; across a fleet, size your endpoint for it. Per the reference,
setting `debug_webhook_url` turns the stream on, so lowering the level thins
the stream rather than stopping it.

## What to change first

Remove `enable_debug_events` from `__init__` and run the verifier. The first
assertion fails because `params` no longer carries the URL, and the platform
has nowhere to send anything. The verifier already renders at levels 1 and 2
itself; to hear level 2 on a call, set `DEBUG_LEVEL=2` in `.env` and run
`python app.py`.
