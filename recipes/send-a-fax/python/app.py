"""Send a fax.

A fax is sent from a document URL with one REST call to the Compatibility Faxes
endpoint. Delivery takes minutes and the outcome - pages sent, or a failure -
arrives on StatusCallback, not in the create response.

Written against signalwire-sdk 3.0.1 (RestClient.compat.faxes) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)
client = RestClient()

FROM = os.getenv("SIGNALWIRE_FAX_NUMBER", "+15550001111")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

FINAL = {"delivered", "failed", "no-answer", "busy", "canceled"}
outcomes = {}


def send(to, media_url, quality="fine"):
    """Queue the fax. Returns the fax sid; the result comes to /fax-status."""
    fax = client.compat.faxes.create(
        To=to,
        From=FROM,
        MediaUrl=media_url,          # a publicly fetchable PDF
        Quality=quality,
        StatusCallback=f"{PUBLIC_URL}/fax-status",
    )
    return fax.get("sid")


@app.post("/fax-status")
def fax_status():
    f = request.form
    sid, status = f.get("FaxSid"), f.get("FaxStatus")
    if status in FINAL:
        outcomes[sid] = {"status": status, "pages": f.get("NumPages"),
                         "error": f.get("ErrorCode")}
    return "", 204


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
