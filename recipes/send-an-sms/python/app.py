"""Send an SMS, and treat the status callback as the truth.

The send response says "queued" or "accepted". Delivery, undelivered and failed
arrive later on the status callback - and a callback can arrive more than once,
so the handler is idempotent on (sid, status).

Written against signalwire-sdk 3.0.1 (the Compatibility Messages endpoint via
RestClient.compat).
"""
import os

from dotenv import load_dotenv
from flask import Flask, request
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

app = Flask(__name__)

# RestClient reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
# from the environment when not passed explicitly.
client = RestClient()

TERMINAL = {"delivered", "undelivered", "failed"}
seen = set()


def send(to, body):
    """Accepted is not delivered. Return the sid and wait for the callback."""
    msg = client.compat.messages.create(
        From=os.environ["SIGNALWIRE_PHONE_NUMBER"],
        To=to,
        Body=body,
        StatusCallback=os.environ["PUBLIC_URL"] + "/sms-status",
    )
    app.logger.info("accepted sid=%s status=%s", msg.get("sid"), msg.get("status"))
    return msg.get("sid")


@app.post("/sms-status")
def sms_status():
    sid = request.form.get("MessageSid")
    status = request.form.get("MessageStatus")
    # Callbacks can repeat. Same (sid, status) twice must do nothing twice.
    key = (sid, status)
    if key in seen:
        return "", 204
    seen.add(key)
    if status in TERMINAL:
        on_terminal(sid, status, request.form.get("ErrorCode"))
    return "", 204


def on_terminal(sid, status, error_code):
    """Runs exactly once per (sid, terminal status). Put your side effects here."""
    app.logger.info("terminal sid=%s status=%s err=%s", sid, status, error_code)


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
