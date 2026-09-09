"""Receive an inbound fax.

A fax-capable number runs this SWML: `receive_fax` answers the fax tone and
takes the document. When it completes, SignalWire POSTs the result - pages,
success, result text and the document URL - to status_url, where the Flask
route below stores it.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")

app = Flask(__name__)


def build(service=None):
    service = service or SWMLService(name="fax-in", route="/fax")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("receive_fax", {"status_url": f"{PUBLIC_URL}/fax-received"})
    service.add_verb("hangup", {})
    return service


@app.route("/fax", methods=["GET", "POST"])
def swml():
    return jsonify(build().get_document())


received = {}


@app.post("/fax-received")
def fax_received():
    p = request.get_json(silent=True) or request.form.to_dict()
    params = p.get("params", p)  # fax fields may be nested under params
    call_id = p.get("call_id", "unknown")
    if str(params.get("success")).lower() == "true" or params.get("success") is True:
        received[call_id] = {
            "pages": params.get("pages"),
            "document": params.get("document") or params.get("url"),
            "from": p.get("from") or params.get("remote_identity"),
        }
    return "", 204


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
