# Register a SIP endpoint and receive calls

> A subscriber's SIP credential is a username and password a softphone registers with, created with one POST. A SWML `connect` to the subscriber's Fabric address is the document that sends a call to it.

**Scenario:** a shop that wants the workshop's desk phone on a SIP softphone, reached from the main number

## What this demonstrates

The vendored REST spec's
`POST /api/fabric/resources/subscribers/{fabric_subscriber_id}/sip_endpoints`
"Create Subscriber SIP credential" requires exactly `username` and `password`. It also takes
`caller_id`, `send_as`, `ciphers`, `codecs` and `encryption`, whose values are
`required`, `optional` or `default`. The subscriber it hangs off is one
`POST /api/fabric/resources/subscribers` with an `email`, and
`GET /api/fabric/resources/{id}/addresses` lists the subscriber's Fabric
address. The bundled schema lists a "Call Fabric Resource address" among the
forms `connect.to` takes. A document that connects to that address therefore
sends a call to whatever registered with the credential. Whether it rings is
the platform's side of a live call. You reach the REST calls as
`client.fabric.subscribers.create`, `list_addresses` and `create_sip_endpoint`.

## How it works

```python
def add_sip_credential(subscriber_id, username=SIP_USERNAME, password=SIP_PASSWORD,
                       caller_id=CALLER_ID):
    if not password:
        raise SystemExit("SIP_PASSWORD is required; see .env.example")
    return client.fabric.subscribers.create_sip_endpoint(
        subscriber_id, username=username, password=password, caller_id=caller_id)

def ring(address, service=None):
    service = service or SWMLService(name="ring", route="/ring")
    service.add_verb("answer", {})
    service.add_verb("connect", {"to": address, "timeout": 30})
    service.add_verb("hangup", {})
    return service
```

What the platform receives:

```http
POST /api/fabric/resources/subscribers
{"email": "workshop@ridgeline.example", "display_name": "Workshop desk"}

GET /api/fabric/resources/<resource_id>/addresses

POST /api/fabric/resources/subscribers/<resource_id>/sip_endpoints
{"username": "workshop-desk", "password": "<from SIP_PASSWORD>", "caller_id": "+1555XXXXXXX"}
```

And the document a number runs, with the address from the listing:

```json
{"version": "1.0.0", "sections": {"main": [
  {"answer": {}}, {"connect": {"to": "/private/workshop", "timeout": 30}}, {"hangup": {}}]}}
```

The function reads the password from `SIP_PASSWORD` when it runs, and a missing
one stops the call before any request. The recipe leaves `ciphers`, `codecs` and
`encryption` at the platform's defaults; set them when your softphone needs a
particular one.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, SIP_USERNAME, SIP_PASSWORD, SIP_CALLER_ID
python app.py subscriber                 # once: prints the resource id and the address
python app.py credential <resource_id>   # once: the SIP credential
python app.py document /private/workshop # the SWML, to serve from a number's webhook
```

There is no server to expose here; the script speaks to the REST API and
exits. Register your softphone with the username, the password and the SIP
domain your Dashboard shows for the Space. Serve the document from any SWML
webhook, point the main number at it, and call.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder that answers with a resource, one
address and one credential. You call the helpers and assert the following.

- `create_subscriber` makes one `POST` to the documented subscribers path with exactly `email` and `display_name`, then one `GET` of its addresses with no body or query
- `add_sip_credential` makes one `POST` to the documented subscriber SIP endpoints path with exactly `username`, `password` and `caller_id`
- with no password it stops with a message naming `SIP_PASSWORD`, and makes no request
- the spec requires exactly `username` and `password` there, documents `caller_id`, `send_as`, `ciphers`, `codecs` and `encryption`, and gives `encryption` exactly three values
- the spec's `201` response carries `id`, `username`, `caller_id` and `encryption`; the subscriber requires exactly `email`
- the document validates, its verbs are `answer`, `connect`, `hangup`, and `connect` is exactly the address with a 30-second timeout
- the bundled schema lists a Call Fabric Resource address among the forms `connect.to` takes

## Limitations

You prove the requests, the shapes and the document. Whether the softphone
registers and rings, and which SIP domain it registers against, are the
platform's side. The domain is in your Dashboard, not in the vendored spec.

The spec also documents `POST /api/fabric/resources/sip_endpoints`, a
credential that is not under a subscriber. Its documented required list
includes fields a create cannot supply, such as `id`, so this recipe uses the
subscriber form.

## What to change first

Pass `encryption="required"` in `add_sip_credential` and run the verifier. The
exact-body assertion fails, and the enum assertion says the value is legal. Put
it in the expected body too, and the same document rings a softphone that only
registers over TLS.
