"""Register a 10DLC brand and campaign, then assign numbers.

US A2P messaging from local numbers requires a registered brand (who you are)
and campaign (what you send). Both are REST resources; number assignment is an
order; carrier review is asynchronous and reported to status_callback_url.

Written against signalwire-sdk 3.0.1 (RestClient.registry) and Flask.

    python app.py register +15550001111 +15550001112
"""
import os
import sys

from dotenv import load_dotenv
from flask import Flask, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)
client = RestClient()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
STATUS_URL = f"{PUBLIC_URL}/10dlc-status"

BRAND = {
    "name": "Acme Coffee",
    "company_name": "Acme Coffee Roasters LLC",
    "contact_email": "compliance@acme.example",
    "contact_phone": "+15550009999",
    "ein": "12-3456789",
    "ein_issuing_country": "US",
    "legal_entity_type": "PRIVATE_PROFIT",
    "company_vertical": "RETAIL",
    "company_website": "https://acme.example",
    "company_address": "1 Bean St, Portland, OR 97201",
    "status_callback_url": STATUS_URL,
}

CAMPAIGN = {
    "name": "Order notifications",
    "sms_use_case": "ACCOUNT_NOTIFICATION",
    "description": ("Transactional order confirmations and pickup-ready notices "
                    "for customers who ordered online."),
    "sample1": "Acme Coffee: your order #4821 is confirmed. Reply STOP to opt out.",
    "sample2": "Acme Coffee: order #4821 is ready for pickup at 1 Bean St.",
    "message_flow": "Customers opt in at checkout by ticking 'text me order updates'.",
    "opt_in_message": ("You are subscribed to Acme Coffee order updates. "
                       "Reply STOP to opt out, HELP for help."),
    "opt_out_message": "You have been unsubscribed from Acme Coffee updates.",
    "help_message": ("Acme Coffee order updates. Email support@acme.example for help. "
                     "Reply STOP to opt out."),
    "embedded_link": False,
    "embedded_phone": False,
    "age_gated_content": False,
    "direct_lending": False,
    "lead_generation": False,
    "status_callback_url": STATUS_URL,
}


def register(numbers):
    """Brand -> campaign -> number order. Returns the three resource dicts."""
    brand = client.registry.brands.create(**BRAND)
    campaign = client.registry.brands.create_campaign(brand["id"], **CAMPAIGN)
    order = client.registry.campaigns.create_order(
        campaign["id"], phone_numbers=list(numbers), status_callback_url=STATUS_URL)
    return brand, campaign, order


states = {}


@app.post("/10dlc-status")
def status():
    """Carrier review outcomes arrive here: brand, campaign and order state changes."""
    p = request.get_json(silent=True) or request.form.to_dict()
    states[p.get("id")] = {"type": p.get("type") or p.get("object"),
                           "state": p.get("state")}
    return "", 204


if __name__ == "__main__":
    if sys.argv[1:2] == ["register"]:
        brand, campaign, order = register(sys.argv[2:])
        print("brand", brand["id"], "campaign", campaign["id"], "order", order["id"])
    else:
        app.run(port=int(os.getenv("PORT", "8080")))
