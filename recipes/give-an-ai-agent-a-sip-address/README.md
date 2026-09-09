# Give an AI agent a SIP address

> One `POST /api/fabric/sip_addresses` with a URL-safe name and the agent's resource id gives a hosted agent a SIP URI. A SIP phone or PBX dials it; no phone number is involved.

**Scenario:** a PBX admin wants to dial the AI receptionist from any desk phone as an extension

## What this demonstrates

A hosted resource is reachable two ways: by a phone number pointed at it, or by
a SIP address. This recipe makes the second one. The response carries the
`uri`, and that string is the whole integration on the PBX side.

The vendored REST spec, `tools/openapi/rest.json`, is the authority.

- `POST /api/fabric/sip_addresses` requires `name` and
  `calling_handler_resource_id`. The name is "lowercase letters, numbers, and
  hyphens only" and "is used to build the address's SIP URI". The recipe
  refuses anything else before sending.
- `user` defaults to `*`, which "accepts any username". Set it when the PBX
  should reach the agent by one specific username.
- `encryption` is `required`, `optional` or `forbidden`. The recipe asks for
  `required`.
- `codecs` defaults to `PCMU` and `PCMA`, and `ip_auth_enabled` to false. The
  recipe leaves both alone.

Neither SDK wraps this path in the versions pinned here. The request goes
through the HTTP client every namespace shares, as the subproject recipes do.

## How it works

```python
NAME_SHAPE = re.compile(r"^[a-z0-9-]+$")

def give_address(resource_id, name, user=None, encryption="required"):
    if not NAME_SHAPE.match(name):
        raise ValueError(...)
    body = {"name": name, "calling_handler_resource_id": resource_id,
            "encryption": encryption}
    if user:
        body["user"] = user
    return http.post("/api/fabric/sip_addresses", body=body)
```

What the platform receives:

```json
{"name": "front-desk",
 "calling_handler_resource_id": "0b7a2f3e-9c41-4d6e-8a52-1f0e3d2c4b5a",
 "encryption": "required"}
```

The response's `uri` is what you dial. Its `context` says which domain the
address lives under, `public` for the project's default. With the default
`user`, any username at that domain reaches the agent. With `user` set, only
that one does.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space
python app.py <agent_resource_id> front-desk
```

The TypeScript surface is the same request on `@signalwire/sdk`, on Node
20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start <agent_resource_id> front-desk
```

The resource id comes from
[Create a hosted voice AI agent with one REST call](../create-a-hosted-voice-ai-agent-with-one-rest-call/).
The script prints the URI; put it in the PBX as a trunk or an extension.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier swaps the SDK's HTTP layer for a recorder, creates two addresses,
and asserts the following.

- four names the spec would reject, with a space, an underscore, capitals, or nothing, raise before any request is made
- the spec requires exactly `name` and `calling_handler_resource_id`, and every key sent is documented
- the first body carries the two required fields and `encryption: required`; the second adds `user: reception`
- the spec's name rule, the `*` default and its meaning, the encryption enum, the codec defaults and the IP-auth default are what the README says they are
- the response schema documents `uri` as the full SIP URI, and the recipe returns it as the dial string
- the TypeScript surface sends the same two bodies and refuses the same four names

## Limitations

The verifier proves the request, not the call. Whether a given PBX accepts the
URI, negotiates SRTP and reaches the agent is live behaviour.

`password` is write-only and never returned. A registration password belongs in
your secrets, not in this recipe's arguments.

## What to change first

Change `encryption="required"` to `"always"` and run the verifier. The exact
body comparison fails on a value outside the enum, which is the point. Three
values are the whole vocabulary.
