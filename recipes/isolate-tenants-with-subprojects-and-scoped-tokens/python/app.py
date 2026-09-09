"""Isolate tenants with subprojects and scoped tokens.

Two requests per tenant. `POST /api/projects` creates a subproject. The
vendored REST spec requires one field, `name`, and its 201 response schema
carries `id`, `subproject` and `parent_project_id`. `POST /api/project/tokens`
then creates an API token whose `subproject_id` is that id and whose
`permissions` list is exactly what you pass. The spec's
`Project.TokenPermission` enum is the whole vocabulary: calling, chat,
datasphere, fax, management, messaging, numbers, pubsub, storage, tasking,
video. A tenant token here gets messaging and calling, and not management.

The spec documents no GET for tokens, so this recipe reads the token value
from the create response and never fetches it again. Store it then.

Written against signalwire-sdk 3.0.1 (RestClient.project.tokens).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

# 3.0.1 wraps the tokens path (client.project.tokens) but not POST /api/projects,
# so the subproject goes through the HTTP client every namespace shares
http = client._http

# what a tenant's token may do; management is deliberately absent
PERMISSIONS = ["messaging", "calling"]


def create_tenant(name, permissions=PERMISSIONS):
    """A subproject and one token bound to it. Returns the ids and the token."""
    project = http.post("/api/projects",
                        body={"name": name, "force_https_requests": True})
    token = client.project.tokens.create(name=f"{name} api",
                                         permissions=list(permissions),
                                         subproject_id=project["id"])
    return {"project_id": project["id"], "token_id": token["id"],
            "permissions": token["permissions"], "token": token["token"]}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: python app.py <tenant name>")
    tenant = create_tenant(sys.argv[1])
    # the token is shown once; this is that once
    print(tenant)
