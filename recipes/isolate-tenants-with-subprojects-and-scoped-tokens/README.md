# Isolate tenants with subprojects and scoped tokens

> One POST creates a subproject, and a second creates an API token bound to it through `subproject_id` with exactly the permissions you list. The spec's permission enum is the whole vocabulary, and `management` is not in this token's list.

**Scenario:** a SaaS that gives each customer their own numbers, logs and credentials on one SignalWire account

## What this demonstrates

`POST /api/projects` creates a subproject. The vendored REST spec requires one
field, `name`, and its `201` response schema carries `id`, `subproject` and
`parent_project_id`. `POST /api/project/tokens` creates an API token. The spec
requires `name` and `permissions`, and takes `subproject_id` to bind the token
to a subproject. `permissions` is a list drawn from the spec's
`Project.TokenPermission` enum: calling, chat, datasphere, fax, management,
messaging, numbers, pubsub, storage, tasking and video. The spec documents no
GET for tokens, so you read the token value from the create response and never
fetch it again.

The SDK wraps the token path as `client.project.tokens.create`. It has no
wrapper for `POST /api/projects` in 3.0.1, so that request goes through the
HTTP client every namespace shares.

## How it works

```python
PERMISSIONS = ["messaging", "calling"]

def create_tenant(name, permissions=PERMISSIONS):
    project = http.post("/api/projects", body={"name": name, "force_https_requests": True})
    token = client.project.tokens.create(name=f"{name} api", permissions=list(permissions),
                                         subproject_id=project["id"])
    return {"project_id": project["id"], "token_id": token["id"],
            "permissions": token["permissions"], "token": token["token"]}
```

What the platform receives:

```json
POST /api/projects
{"name": "Ridgeline Cycles", "force_https_requests": true}

POST /api/project/tokens
{"name": "Ridgeline Cycles api", "permissions": ["messaging", "calling"],
 "subproject_id": "<id from the first response>"}
```

`force_https_requests` is one of four booleans the project create takes; the
spec says webhooks and callbacks for the project must then use HTTPS. The
token's list leaves out `management`, the permission this script's own token
needs to create projects and tokens. What the platform refuses a token without
it is the platform's enforcement, not this recipe's proof.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your parent project's credentials
python app.py "Ridgeline Cycles"
```

You expose no server; the script speaks to the REST API and exits. It prints
the token once. Store it in the tenant's secrets then, because the spec
documents no request that returns it again.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder that answers the project create
with an id and the token create with a token. You call `create_tenant` with a
three-permission list that is not the default, and assert the following.

- it makes two `POST`s in order, to the documented projects path and the documented tokens path
- the project body is exactly `name` and `force_https_requests`
- the token body is exactly `name`, the three permissions you passed, and a `subproject_id` equal to the id the first response carried
- the spec's required fields are exactly `name` on the project and `name` plus `permissions` on the token
- every permission sent is in the spec's enum, and the enum is exactly the eleven names above
- the spec's `201` project response carries `id`, `subproject` and `parent_project_id`; its token response carries `id`, `token` and `permissions`
- the spec documents no `GET` on either tokens path, and documents `POST /api/projects/{id}/signing-key/rotate`

## Limitations

You prove the requests and the documented shapes. What a token bound to one
subproject can see of another is the platform's enforcement, and this recipe
does not exercise it. Treat the isolation as a property to test against your
account, not one this folder proves.

The spec's project response also carries `signing_key`, and it documents
`POST /api/projects/{id}/signing-key/rotate`, titled "Rotate a project's
signing key". You verify the path exists; you do not call it here.

## What to change first

Pass `["management"]` as the permissions in `create_tenant` and run the
verifier. The exact-body assertion fails, because the verifier pins the list
it passed. A tenant's token should not carry the permission that creates
tenants.
