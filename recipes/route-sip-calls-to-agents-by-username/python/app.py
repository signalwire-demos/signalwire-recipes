"""Route SIP calls to agents by username.

One AgentServer, two agents, one SIP domain. A routing callback registered on
each agent reads the SIP username out of the platform's request body with
`SWMLService.extract_sip_username`. It answers with the route of the agent
that owns the username. The SDK turns that answer into a 307 redirect, so
`sip:workshop@your-domain` reaches the support agent and `sip:sales@...`
reaches sales, from one webhook path.

In 3.0.1 you have to register the callback on each agent before
`server.register()`, because that call copies the agent's routes into the app
once. `AgentServer.setup_sip_routing()` registers its callback after that copy
and mounts nothing, so this recipe does the registration itself.

Written against signalwire-sdk 3.0.1 (AgentServer, register_routing_callback).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, AgentServer, SWMLService

# the SDK does not read .env for you
load_dotenv()

# SIP username -> agent route. The router ignores the domain part of the URI.
USERNAMES = {"sales": "/sales/", "orders": "/sales/", "support": "/support/",
             "workshop": "/support/"}
SIP_PATH = "/sip"


def route_by_username(request, body):
    """The routing callback: a route to redirect to, or None to stay put."""
    username = SWMLService.extract_sip_username(body)
    return USERNAMES.get((username or "").lower())


class DeskAgent(AgentBase):
    def __init__(self, name, route, role):
        super().__init__(name=name, route=route)
        self.prompt_add_section("Role", role)
        # before server.register(): that call copies the routes once
        self.register_routing_callback(route_by_username, path=SIP_PATH)


def build_server(port=None):
    server = AgentServer(port=port or int(os.getenv("PORT", "3000")))
    server.register(DeskAgent("sales", "/sales",
                              "You are the sales desk for Ridgeline Cycles."), "/sales")
    server.register(DeskAgent("support", "/support",
                              "You are the workshop support desk for Ridgeline Cycles."),
                    "/support")
    return server


if __name__ == "__main__":
    build_server().run()
