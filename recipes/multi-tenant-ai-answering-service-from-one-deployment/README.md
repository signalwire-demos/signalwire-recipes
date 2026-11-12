# Multi-tenant AI answering service: one deployment answering as many businesses, configured per request

> An agency answering service demo built to show per-request configuration instead of a deployment per customer. The callback resolves the tenant and registers only its tools, so another tenant's tool does not exist in the SWML.

**Scenario:** A caller to the dental office hears the dental office and a caller to the HVAC company hears the HVAC company, each with its own voice, hours and tools

## What this demonstrates

Per-request configuration instead of one deployment per customer.
`set_dynamic_config_callback` runs on every request, the SWML fetch and every
SWAIG call, against a per-request copy of the agent. The callback resolves the
tenant on the server and registers only that tenant's tools, so a tool enabled
for one tenant does not exist for another. It is not hidden by the prompt; it
is absent from the SWML, and a SWAIG call to it gets "not found". Handlers
read the tenant, hours and transfer numbers from the YAML, bound in a closure,
never from model arguments. `transfer_call` accepts only the target names in
that tenant's `transfer_targets` (an enum), refuses outside office hours, and
dials the number from `.env`.

An agency runs one app for every client. When a call comes in, the app works
out which business was called, by the called number or `?tenant=<id>` on the
webhook URL. It loads that business's `tenants/<id>.yaml` and answers as that
business. The three sample tenants are a dental office, an HVAC company and a
law firm. The dental office takes appointment requests and transfers to the
front desk. The HVAC company connects emergencies to the on-call technician at
any hour. The law firm takes consultation requests by practice area. A call to
an unknown number gets a neutral answering service that can only take a
message.

## How it works

`add_swaig_query_params({"tenant": id})` keeps SWAIG callbacks on the same
tenant. Tenant files are read on each request, so adding a client is copying
a YAML file into `tenants/` with no redeploy. `${VAR}` expands only inside
`numbers` and `transfer_targets`; anywhere else, a prompt say, it stays
literal. A tenant file cannot pull a secret like the API token into the
SWML. A new kind of tool is one entry in `TOOLS` in `app.py`, and it reaches
only the tenants that list it.

Where each mechanism lives in the repository:

- `set_dynamic_config_callback`: `app.py`, `AnsweringServiceAgent.__init__` and `configure()`
- server-side tenant resolution (number, then `?tenant=`, then default): `app.py`, `resolve_tenant()`
- per-tenant `define_tool` from a registry: `app.py`, `TOOLS` and `configure()`
- `add_swaig_query_params`: `app.py`, `configure()`
- `connect` to a YAML or `.env` number only: `app.py`, `transfer_to()`
- the tenant config (prompt, voice, hours, tools, targets): `tenants/*.yaml`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and three tenant files. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Serverless works for the agent itself, but move `MESSAGES_FILE` to a real
store first, since function filesystems are ephemeral. `ALLOW_TENANT_QUERY`
should be off in production, so a caller cannot pick a tenant through the URL.
The recipes `configure-an-agent-per-request` and
`split-one-number-into-isolated-personas` are the verified 3.0.1 versions of
the two ideas this build combines.

## What to change first

The tenant YAML schema is the thing to make yours. Copy `tenants/dental.yaml`
to `tenants/<id>.yaml` (the file name must equal `id`) and set `numbers`,
`name`, `voice`, `timezone`, `hours`, `prompt`, `tools` (names from `TOOLS` in
`app.py`) and `transfer_targets`. Then open `config.py`: `DEFAULT_TENANT`
decides what an unknown caller gets, `ALLOW_TENANT_QUERY=False` turns off
`?tenant=` routing, and `MESSAGES_FILE` is where messages go.
