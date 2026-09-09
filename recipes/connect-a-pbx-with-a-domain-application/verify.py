"""Prove the claim without a network.

Claim: an IP-authenticated Domain Application takes inbound SIP from your PBX
and a SIP Gateway carries calls back to it.

Proof: with the HTTP layer recorded, setup makes two documented requests -
POST /api/relay/rest/domain_applications with ip_auth enabled and our PBX IPs,
handled by our SWML URL; POST /api/fabric/resources/sip_gateways with the PBX
SIP URI and the required encryption/ciphers/codecs - and the two SWML documents
validate and connect where they should.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "PUBLIC_URL": "https://recipes.example.test",
                   "PBX_IPS": "203.0.113.10,203.0.113.11", "PBX_SIP_URI": "sip:pbx.example.com:5060"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"id": "da-1", "domain": "acme-pbx.dapp.signalwire.com"},
        {"id": "gw-1", "name": "acme-pbx-gateway"},
    ]))
    recipe.client._http = rec  # the Domain Application call goes through the raw layer
    dapp = recipe.create_domain_application()
    gw = recipe.create_sip_gateway()
    assert dapp["domain"].endswith(".dapp.signalwire.com") and gw["id"] == "gw-1"

    da, sg = rec.calls
    assert (da["method"], da["path"]) == ("POST", "/api/relay/rest/domain_applications"), da
    V.assert_documented("rest", "POST", da["path"], body=da["body"])
    assert da["body"]["ip_auth_enabled"] is True and da["body"]["ip_auth"] == ["203.0.113.10", "203.0.113.11"]
    assert da["body"]["call_handler"] == "relay_script"
    assert da["body"]["call_request_url"] == "https://recipes.example.test/from-pbx"

    assert (sg["method"], sg["path"]) == ("POST", "/api/fabric/resources/sip_gateways"), sg
    V.assert_documented("rest", "POST", sg["path"], body=sg["body"])
    assert sg["body"]["uri"] == "sip:pbx.example.com:5060"

    inbound = recipe.build_from_pbx().get_document()
    outbound = recipe.build_to_pbx().get_document()
    for d in (inbound, outbound):
        V.validate_swml(d)
    assert V.first(inbound, "connect")["to"] == "${call.to}", inbound
    assert V.first(outbound, "connect")["to"] == "/private/acme-pbx-gateway", outbound
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    assert set(y["sections"]) == {"main", "to_pbx"}, set(y["sections"])
    print("ok: POST domain_applications(ip_auth, relay_script) + POST sip_gateways(uri); SWML bridges both directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
