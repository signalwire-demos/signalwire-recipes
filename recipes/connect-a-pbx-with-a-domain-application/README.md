# Connect a PBX with a Domain Application

> An IP-authenticated Domain Application takes inbound SIP from your PBX and a SIP Gateway carries calls back to it.

**Scenario:** an office PBX that keeps its extensions and gets SignalWire's PSTN, AI and SWML behind them

## What this demonstrates

Bring-your-own-PBX is two resources, both created over REST. **Inbound** (PBX → SignalWire): a *Domain Application* is a SIP domain,
`<identifier>.dapp.signalwire.com`. It accepts INVITEs from the IP addresses you list
and runs a SWML document for each call. **Outbound** (SignalWire → PBX): a *SIP Gateway* is a Fabric resource with an address
(`/private/<name>`) that any SWML can `connect` to. SignalWire delivers the call to
the PBX's SIP URI. Neither side needs SIP
registration or credentials: the PBX trusts by IP, SignalWire trusts by IP.

## How it works

```python
client._http.post("/api/relay/rest/domain_applications", body={
    "name": "Acme PBX inbound", "identifier": "acme-pbx",
    "ip_auth_enabled": True, "ip_auth": ["203.0.113.10", "203.0.113.11"],
    "call_handler": "relay_script", "call_request_url": f"{PUBLIC_URL}/from-pbx",
    "encryption": "optional", "codecs": ["PCMU", "PCMA", "OPUS"]})

client.fabric.sip_gateways.create(name="acme-pbx-gateway", uri="sip:pbx.example.com:5060",
                                  encryption="optional", ciphers=[...], codecs=[...])
```

The Domain Application bridges the incoming call with `connect`, using `${call.to}` as
the destination. That value is the PSTN number the PBX dialled. In the other
direction, the SWML a PSTN number runs to reach the PBX is `connect: { to:
"/private/acme-pbx-gateway" }`.
Put an `ai` verb in either document and the PBX has an AI agent behind an
extension.

The typed `RestClient` wraps SIP Gateways but not Domain Applications, so that
one call goes through the client's authenticated HTTP layer by path. Registering
individual SIP phones instead of a trunk is `register-a-sip-endpoint-and-receive-calls`;
a FreeSWITCH box has its own connector resource (`connect-freeswitch-to-signalwire`).

## Run it

```bash
cd python
pip install -r requirements.txt
export SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=...
export PBX_IPS=203.0.113.10 PBX_SIP_URI=sip:pbx.example.com:5060 PUBLIC_URL=https://<your-host>
export SWML_BASIC_AUTH_USER=signalwire SWML_BASIC_AUTH_PASSWORD=choose-something-long
python app.py setup      # prints the SIP domain for the PBX and the gateway address for SWML
python app.py            # serves the inbound SWML at /from-pbx
```

On the PBX, add a trunk to the printed `.dapp.signalwire.com` domain. Point a
SignalWire number's SWML webhook at a document that connects to the gateway
address (the `to_pbx` section of `swml/agent.yaml`). The served document sits
behind the basic-auth credentials above, so a webhook URL into this app carries
them as `https://<user>:<password>@<your-host>/from-pbx/`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer recorded, setup must make exactly the two documented requests,
with the documented required fields checked against `tools/openapi/rest.json`. The
verifier also asserts:

- IP auth is enabled with our PBX addresses
- our SWML URL is the handler
- both SWML documents validate and connect in the right direction

## What to change first

Replace `connect: { to: "${call.to}" }` in the inbound document with an `ai`
verb: every extension on the PBX can now dial an AI agent by number.
