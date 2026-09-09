"""Configure an agent per request.

One deployed agent serves many tenants. `set_dynamic_config_callback`
registers a function that runs on every SWML request with the query string,
the POST body and the headers. It receives an ephemeral copy of the agent and
configures that copy: prompt sections, voice, global_data. The document the
platform gets is rendered from the copy, and the agent you deployed is left as
it was for the next request.

Point each tenant's number at the same host with a different query string:
`https://<user>:<password>@host/front-desk/?tenant=harbor`. The trailing slash
matters in 3.0.1. A header, `X-Tenant`, works too.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase

# the SDK does not read .env for you
load_dotenv()

# What differs per tenant. In production this is a database row keyed by the
# tenant id; here it is a dict so the recipe runs from a clone.
TENANTS = {
    "ridgeline": {
        "name": "Ridgeline Cycles",
        "voice": "rime.spore",
        "hours": "8 to 6, Monday to Saturday",
    },
    "harbor": {
        "name": "Harbor Bike Repair",
        "voice": "rime.marisol",
        "hours": "10 to 7, every day",
    },
}
DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", "ridgeline")


def configure(query_params, body_params, headers, agent):
    """Runs on every request, against an ephemeral copy of the agent."""
    key = (query_params.get("tenant") or headers.get("x-tenant")
           or DEFAULT_TENANT).lower()
    tenant = TENANTS.get(key) or TENANTS[DEFAULT_TENANT]
    if key not in TENANTS:
        key = DEFAULT_TENANT
    agent.prompt_add_section(
        "Tenant",
        f"You answer for {tenant['name']}. Opening hours are {tenant['hours']}. "
        "Never mention any other shop.",
    )
    agent.add_language("English", "en-US", tenant["voice"])
    agent.set_global_data({"tenant": key, "shop": tenant["name"]})


class FrontDeskAgent(AgentBase):
    def __init__(self):
        super().__init__(name="front-desk", route="/front-desk")
        # Everything every tenant shares lives here, on the deployed agent.
        self.prompt_add_section(
            "Role",
            "You are a bicycle shop's front desk. Answer questions about hours "
            "and take a message for anything else.",
        )
        self.set_dynamic_config_callback(configure)


agent = FrontDeskAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
