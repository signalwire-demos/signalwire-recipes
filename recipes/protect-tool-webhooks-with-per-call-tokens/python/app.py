"""Protect tool webhooks with per-call tokens.

Every tool webhook URL the platform receives carries a token minted for this
call and this function: an HMAC over call id, function name, expiry and a
nonce, signed with a key that lives only in your process. The SDK refuses a
token minted for another call, for another function, after expiry, or with a
character changed.

The SDK checks a token only when one is present. A request that omits it, or
sends an empty one, is not refused by the token layer, and the basic-auth
credentials that would refuse it are embedded in the same URL an attacker
captured. So this agent adds one rule of its own, on the app the SDK builds: a
request to the tool endpoint with no token is refused before any handler runs.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# How long a token stays valid after the document is served. The SDK default
# is an hour (token_expiry_secs=3600); this recipe shortens it to fifteen
# minutes. A call that can run longer needs a longer window.
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "900"))

ACCOUNTS = {"48815": {"name": "Dana Whitfield", "balance": 42.10}}

# Every handler run is recorded here, so a test can prove a refused request
# never reached one.
HANDLER_RUNS = []


class AccountAgent(AgentBase):
    def __init__(self):
        # token_expiry_secs sizes the window every per-call token is valid for
        super().__init__(name="accounts", route="/accounts",
                         token_expiry_secs=TOKEN_TTL_SECONDS)
        self.prompt_add_section(
            "Role",
            "You help callers with their account at a bicycle shop. Look the "
            "account up before quoting anything. Only refund when asked.",
        )

    # secure=True is the default on every tool below: each one's webhook URL
    # carries a token bound to the call the document was rendered for.

    @AgentBase.tool(
        name="get_balance",
        description="Look up an account's balance by account number.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string",
                               "description": "The five digit account number."}
            },
            "required": ["account_id"],
        },
    )
    def get_balance(self, args, raw_data):
        HANDLER_RUNS.append("get_balance")
        acct = ACCOUNTS.get((args.get("account_id") or "").strip())
        if not acct:
            return FunctionResult("NOT_FOUND: no such account. Ask for the "
                                  "number again.")
        return FunctionResult(f"{acct['name']} has a balance of "
                              f"{acct['balance']:.2f}.")

    @AgentBase.tool(
        name="issue_refund",
        description="Refund the account's balance to the card on file.",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string",
                               "description": "The five digit account number."}
            },
            "required": ["account_id"],
        },
    )
    def issue_refund(self, args, raw_data):
        HANDLER_RUNS.append("issue_refund")
        acct = ACCOUNTS.get((args.get("account_id") or "").strip())
        if not acct:
            return FunctionResult("NOT_FOUND: no such account.")
        # A real handler would call your payments API here.
        return FunctionResult(f"Refunded {acct['balance']:.2f} to the card on "
                              f"file for {acct['name']}.")


def build():
    """The agent, plus the one rule the SDK leaves to you."""
    agent = AccountAgent()
    app = agent.get_app()
    tool_path = agent.route.rstrip("/") + "/swaig"

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        # The SDK validates a token when one is present. This closes the gap
        # where a request carries none, or an empty one: it never reaches a
        # handler. `not ...get()` refuses both; a key check alone would let
        # `?__token=` through, and the SDK treats an empty value as absent.
        if request.url.path.rstrip("/") == tool_path and request.method == "POST":
            if not request.query_params.get("__token"):
                return JSONResponse(
                    status_code=403,
                    content={"response": "A per-call token is required."},
                )
        return await call_next(request)

    return agent


agent = build()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
