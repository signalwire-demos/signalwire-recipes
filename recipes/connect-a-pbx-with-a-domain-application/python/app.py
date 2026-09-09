"""Connect a PBX with a Domain Application.

Inbound from the PBX: a Domain Application is a SIP domain on SignalWire that
accepts INVITEs from your PBX's IP addresses (IP auth) and hands each call to
a SWML document. Outbound to the PBX: a SIP Gateway resource is an address your
SWML can `connect` to, which SignalWire delivers to your PBX's SIP URI.

Written against signalwire-sdk 3.0.1. The typed RestClient wraps SIP Gateways
(fabric.sip_gateways) but not Domain Applications, so that call goes through
the same authenticated HTTP layer by path.

    python app.py setup   # create both resources; print the SIP domain and gateway
"""
import os
import sys

from dotenv import load_dotenv
from signalwire import SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

client = RestClient()

PBX_IPS = os.getenv("PBX_IPS", "203.0.113.10,203.0.113.11").split(",")
PBX_SIP_URI = os.getenv("PBX_SIP_URI", "sip:pbx.example.com:5060")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
# the SIP domain becomes <IDENTIFIER>.dapp.signalwire.com
IDENTIFIER = os.getenv("DOMAIN_IDENTIFIER", "acme-pbx")
GATEWAY_NAME = os.getenv("GATEWAY_NAME", "acme-pbx-gateway")


def create_domain_application():
    """Inbound: PBX -> SignalWire. IP-authenticated; calls run our SWML."""
    return client._http.post("/api/relay/rest/domain_applications", body={
        "name": "Acme PBX inbound",
        "identifier": IDENTIFIER,
        "ip_auth_enabled": True,
        "ip_auth": PBX_IPS,
        "call_handler": "relay_script",
        "call_request_url": f"{PUBLIC_URL}/from-pbx",
        "call_request_method": "POST",
        "encryption": "optional",
        "codecs": ["PCMU", "PCMA", "OPUS"],
    })


def create_sip_gateway():
    """Outbound: SignalWire -> PBX. A Fabric resource with a dialable address."""
    return client.fabric.sip_gateways.create(
        name=GATEWAY_NAME,
        uri=PBX_SIP_URI,
        encryption="optional",
        ciphers=["AEAD_AES_256_GCM_8", "AES_256_CM_HMAC_SHA1_80"],
        codecs=["PCMU", "PCMA", "OPUS"],
    )


def build_from_pbx(service=None):
    """SWML the Domain Application runs for a call arriving from the PBX:
    bridge it to the PSTN number the PBX dialled."""
    service = service or SWMLService(name="from-pbx", route="/from-pbx")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("connect", {"to": "${call.to}"})
    service.add_verb("hangup", {})
    return service


def build_to_pbx(service=None, gateway_address=None):
    """SWML for a PSTN number that should ring into the PBX via the gateway."""
    service = service or SWMLService(name="to-pbx", route="/to-pbx")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("connect", {"to": gateway_address or f"/private/{GATEWAY_NAME}"})
    service.add_verb("hangup", {})
    return service


if __name__ == "__main__":
    if sys.argv[1:] == ["setup"]:
        dapp = create_domain_application()
        gw = create_sip_gateway()
        domain = dapp.get("domain") or f"{IDENTIFIER}.dapp.signalwire.com"
        print("PBX should send INVITEs to:", domain)
        print("SWML can connect to the PBX at:", f"/private/{GATEWAY_NAME}", gw.get("id"))
    else:
        build_from_pbx().serve(port=int(os.getenv("PORT", "8080")))
