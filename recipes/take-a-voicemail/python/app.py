"""Take a voicemail.

`connect` rings the owner. When the bridge does not happen, `result`'s failed
branch plays a prompt and `record` takes the message in the foreground. It
runs until `#`, silence or `max_length`, then execution continues. The
platform POSTs recording events, including the download URL, to `status_url`,
which is an endpoint you run; this app does not serve one. It also sets
`record_url` and `record_result` on the call.

Written against signalwire-sdk 3.0.1 (SWMLService).
"""
import os

from dotenv import load_dotenv
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

OWNER = os.getenv("OWNER_NUMBER", "+15550100001")
RING_SECONDS = int(os.getenv("RING_SECONDS", "20"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")


def build(service=None):
    service = service or SWMLService(name="voicemail", route="/voicemail")
    service.reset_document()

    service.add_verb("answer", {})
    service.add_verb("connect", {
        "to": OWNER,
        "timeout": RING_SECONDS,
        "result": {"case": {
            "connected": [{"hangup": {}}],
            "failed": [
                {"play": {"url": "say:Leave a message after the tone."}},
                {"record": {
                    "beep": True,
                    "format": "mp3",
                    "max_length": 120,
                    "end_silence_timeout": 5,
                    "terminators": "#",
                    "status_url": f"{PUBLIC_URL}/recording-status",
                }},
                {"play": {"url": "say:Thanks. We will call you back."}},
                {"hangup": {}},
            ],
        }},
    })
    return service


if __name__ == "__main__":
    build().serve(port=int(os.getenv("PORT", "8080")))
