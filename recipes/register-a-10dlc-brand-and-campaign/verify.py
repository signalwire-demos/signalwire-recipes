"""Prove the claim without a network.

Claim: a brand and campaign are registered over REST, numbers are assigned to
the campaign, and the status webhook reports carrier approval.

Proof: with the HTTP layer recorded, register() makes exactly three documented
requests in dependency order - POST brands, POST brands/{id}/campaigns, POST
campaigns/{id}/orders - the campaign is created under the returned brand id,
the order under the returned campaign id and carries our numbers and callback;
the webhook records state changes by resource id. (The OpenAPI spec publishes
no body schema for brands/campaigns, so field names are checked against the
documented reference lists instead.)
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "PUBLIC_URL": "https://recipes.example.test"})

import verifylib as V  # noqa: E402

# From docs/apis/rest/campaign-registry/brands/create-brand and campaigns/create-campaign
BRAND_FIELDS = {"name", "company_name", "contact_email", "contact_phone", "ein_issuing_country",
                "legal_entity_type", "ein", "company_address", "company_vertical", "company_website",
                "csp_brand_reference", "csp_self_registered", "status_callback_url"}
CAMPAIGN_FIELDS = {"name", "sms_use_case", "sub_use_cases", "campaign_verify_token", "description",
                   "sample1", "sample2", "sample3", "sample4", "sample5", "dynamic_templates", "message_flow",
                   "opt_in_message", "opt_out_message", "help_message", "opt_in_keywords", "opt_out_keywords",
                   "help_keywords", "number_pooling_required", "number_pooling_per_campaign", "direct_lending",
                   "embedded_link", "embedded_phone", "age_gated_content", "lead_generation", "status_callback_url"}


def main():
    V.sdk_banner()
    import app as recipe
    rec = V.record_everything(recipe.client, V.Recorder(responses=[
        {"id": "brand-1", "state": "pending"},
        {"id": "camp-1", "state": "pending"},
        {"id": "order-1", "state": "pending"},
    ]))
    brand, campaign, order = recipe.register(["+15550001111", "+15550001112"])
    b, c, o = rec.calls
    assert (b["method"], b["path"]) == ("POST", "/api/relay/rest/registry/beta/brands"), b
    V.assert_documented("rest", "POST", b["path"])
    assert set(b["body"]) <= BRAND_FIELDS, set(b["body"]) - BRAND_FIELDS
    assert b["body"]["status_callback_url"] == "https://recipes.example.test/10dlc-status"

    assert (c["method"], c["path"]) == ("POST", "/api/relay/rest/registry/beta/brands/brand-1/campaigns"), c
    V.assert_documented("rest", "POST", c["path"])
    assert set(c["body"]) <= CAMPAIGN_FIELDS, set(c["body"]) - CAMPAIGN_FIELDS
    assert len(c["body"]["description"]) >= 40 and all(len(c["body"][k]) >= 20 for k in ("sample1", "sample2"))

    assert (o["method"], o["path"]) == ("POST", "/api/relay/rest/registry/beta/campaigns/camp-1/orders"), o
    V.assert_documented("rest", "POST", o["path"], body=o["body"])
    assert o["body"]["phone_numbers"] == ["+15550001111", "+15550001112"]

    w = recipe.app.test_client()
    w.post("/10dlc-status", json={"id": "camp-1", "type": "campaign", "state": "approved"})
    assert recipe.states["camp-1"] == {"type": "campaign", "state": "approved"}
    print("ok: POST brands -> POST brands/{id}/campaigns -> POST campaigns/{id}/orders(phone_numbers); status webhook records state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
