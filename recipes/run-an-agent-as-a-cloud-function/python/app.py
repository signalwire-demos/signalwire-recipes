"""Run an agent as a cloud function.

The same agent file serves from a laptop and runs as an AWS Lambda handler
with one line of difference: `agent.run(event, context)`. `run()` reads the
environment to pick a mode. `AWS_LAMBDA_FUNCTION_NAME` means Lambda,
`FUNCTION_TARGET` or `K_SERVICE` mean Google Cloud Functions,
`FUNCTIONS_WORKER_RUNTIME` means Azure and `GATEWAY_INTERFACE` means CGI.
Nothing set means a local server. In Lambda mode it returns the
`{"statusCode", "headers", "body"}` dict API Gateway expects. The body is the
SWML for a request to the root, and the tool result for a POST to `/swaig`.

Basic auth still applies: the event's `Authorization` header must carry the
same credentials the SDK reads from `SWML_BASIC_AUTH_USER` and
`SWML_BASIC_AUTH_PASSWORD`.

Written against signalwire-sdk 3.0.1 (ServerlessMixin, AgentBase.run).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

STOCK = {"SK-2210": 14, "SK-0031": 0}


class StockAgent(AgentBase):
    def __init__(self):
        super().__init__(name="stock", route="/stock")
        self.prompt_add_section(
            "Role",
            "You answer stock questions for a bicycle parts desk. Look the part "
            "up with check_stock before you answer.",
        )

    @AgentBase.tool(
        name="check_stock",
        description="Look up how many of a part are in stock by its SKU.",
        parameters={
            "type": "object",
            "properties": {"sku": {"type": "string",
                                   "description": "The part's SKU, like SK-2210."}},
            "required": ["sku"],
        },
    )
    def check_stock(self, args, raw_data):
        sku = (args.get("sku") or "").strip().upper()
        if sku not in STOCK:
            return FunctionResult(f"NOT_FOUND: no part {sku}. Ask for the SKU again.")
        return FunctionResult(f"{STOCK[sku]} of {sku} in stock.")


agent = StockAgent()


def handler(event, context):
    """The AWS Lambda entry point. Point the function's handler at
    `app.handler`; API Gateway's HTTP API (payload v2) is the shape it reads."""
    return agent.run(event, context)


if __name__ == "__main__":
    # with no serverless environment detected this starts a local server
    agent.run(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
