"""Send an OTP by SMS, with voice fallback.

The MFA API generates the code, delivers it by SMS or by a voice call, and
verifies what the user types back. Your application stores only the request
id; it never sees or stores the code.

Written against signalwire-sdk 3.0.1 (RestClient.mfa) and Flask.

  POST /otp/start   {"to": "+1555..."}                 -> {"request_id": ...}
  POST /otp/voice   {"to": "+1555..."}                 -> {"request_id": ...}  (fallback)
  POST /otp/verify  {"request_id": ..., "token": "..."} -> {"verified": true|false}
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)
client = RestClient()

FROM = os.getenv("SIGNALWIRE_PHONE_NUMBER", "+15550001111")
OPTIONS = {
    "message": "Your verification code is: ",
    "token_length": 6,
    "valid_for": 300,      # seconds
    "max_attempts": 3,
    "allow_alphas": False,
}


def send_by_sms(to):
    res = client.mfa.sms(**{"to": to, "from": FROM, **OPTIONS})
    return res["id"]


def send_by_voice(to):
    """Same code parameters, read out over a phone call."""
    res = client.mfa.call(**{"to": to, "from": FROM, **OPTIONS})
    return res["id"]


def check(request_id, token):
    res = client.mfa.verify(request_id, token=token)
    return bool(res.get("success"))


@app.post("/otp/start")
def start():
    return jsonify(request_id=send_by_sms(request.json["to"]))


@app.post("/otp/voice")
def voice():
    return jsonify(request_id=send_by_voice(request.json["to"]))


@app.post("/otp/verify")
def verify():
    body = request.json
    return jsonify(verified=check(body["request_id"], body["token"]))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
