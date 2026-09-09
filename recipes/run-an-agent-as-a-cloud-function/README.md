# Run a voice AI agent as an AWS Lambda function

> The same agent file runs as an AWS Lambda handler. `agent.run(event, context)` returns the SWML for the root and the tool result for a POST to `/swaig`. Both sit behind the same basic auth, in the shape API Gateway expects.

**Scenario:** a request-driven stock-lookup agent

## What this demonstrates

`AgentBase.run()` picks its mode from the environment. `AWS_LAMBDA_FUNCTION_NAME`
means Lambda, `FUNCTION_TARGET` or `K_SERVICE` mean Google Cloud Functions, and
`FUNCTIONS_WORKER_RUNTIME` means Azure Functions. `GATEWAY_INTERFACE` means CGI,
and nothing means a local server. In Lambda mode it reads an API Gateway event
and returns `{"statusCode", "headers", "body"}`. The mode detection is
`get_execution_mode()` in `core/logging_config.py`; the Lambda branch is
`handle_serverless_request` in `core/mixins/serverless_mixin.py`.

Basic auth does not go away. `_check_lambda_auth` in `core/mixins/auth_mixin.py`
reads the event's `Authorization` header and compares it with the credentials
the SDK took from `SWML_BASIC_AUTH_USER` and `SWML_BASIC_AUTH_PASSWORD`.

## How it works

```python
agent = StockAgent()

def handler(event, context):
    return agent.run(event, context)

if __name__ == "__main__":
    agent.run(host="0.0.0.0", port=3000)      # a local server when nothing else is set
```

What the function returns for a `GET /` with valid credentials:

```json
{"statusCode": 200, "headers": {"Content-Type": "application/json"},
 "body": "{\\"version\\": \\"1.0.0\\", \\"sections\\": {\\"main\\": [...]}}"}
```

For a `POST /swaig` whose body is the platform's tool payload, `body` is the
handler's result: `{"response": "14 of SK-2210 in stock."}`. The Lambda branch
reads `rawPath` (HTTP API payload v2) or `pathParameters.proxy` (REST API v1).
When the event sets `isBase64Encoded`, the SDK decodes the body. It takes the function
name and arguments from the POST body the way the HTTP routes do.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py                    # locally: a server on port 3000
```

To deploy, zip `app.py` with its dependencies and set the function handler to
`app.handler`. Put an API Gateway HTTP API in front with a `$default` route. In
the function's configuration set the two `SWML_BASIC_AUTH_*` variables and
`SWML_PROXY_URL_BASE` to the API Gateway URL. The SDK renders every tool's
`web_hook_url` from that base. Without it, tool calls go to a host the function
does not have. Point a number's SWML webhook at
`https://<user>:<password>@<api-id>.execute-api.<region>.amazonaws.com/`.

## Verify it

No network, no account, no AWS.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier sets `AWS_LAMBDA_FUNCTION_NAME` so `run()` takes the Lambda branch,
builds API Gateway events by hand, and asserts the following.

- `GET /` with the right `Authorization` header returns `statusCode` 200, a JSON content type, and a body that parses and validates as SWML with the one tool
- that tool's `web_hook_url` is `https://<user>:<password>@<the SWML_PROXY_URL_BASE host>/swaig/` with a per-call token, which is what makes tool calls reach the function; in serverless mode the SDK drops the agent's route from the path
- `POST /swaig` with the platform's tool payload returns 200 and the handler's exact result
- the same POST with no header, or with the wrong password, returns 401 with a `WWW-Authenticate` challenge

## Limitations

The verifier proves the Lambda branch on this machine, not a deployment. Cold
starts, timeouts and API Gateway's own configuration are yours to size.

The SDK renders tool webhooks and `post_prompt_url` from the host it computes
in `get_full_url` (`agent_base.py`), which honours `SWML_PROXY_URL_BASE`. A
deployment without it has no working tools; the verifier sets it and checks the
rendered URL.

## What to change first

Delete `AWS_LAMBDA_FUNCTION_NAME` from the verifier's environment and run it.
`run()` no longer detects Lambda and tries to start a server, so the first
assertion never gets a dict back. The mode is the environment, and only the
environment.
