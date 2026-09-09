"""Queue a call until an agent is free.

Three small documents served from one Flask app:

  /caller  answer, then enter_queue("support") with a wait_url for hold audio.
           If nobody takes the call within wait_time, execution continues and
           the caller hears an apology.
  /wait    the hold document; the platform re-runs it while the caller waits.
  /agent   what an agent dials: connect to "queue:support" takes the next
           waiting caller.

Written against signalwire-sdk 3.0.1 (SWMLService) and Flask.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from signalwire import SWMLService

# the SDK does not read .env for you
load_dotenv()

PUBLIC_URL = os.getenv("PUBLIC_URL", "https://your-host.example.com")
QUEUE = os.getenv("QUEUE_NAME", "support")
HOLD_MUSIC = os.getenv("HOLD_MUSIC_URL",
                       "https://cdn.signalwire.com/default-music/welcome.mp3")
MAX_WAIT_SECONDS = int(os.getenv("MAX_WAIT_SECONDS", "600"))

app = Flask(__name__)


def build_caller(service=None):
    service = service or SWMLService(name="queue-caller", route="/caller")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("play", {
        "url": "say:All of our agents are busy. Please stay on the line."})
    service.add_verb("enter_queue", {
        "queue_name": QUEUE,
        "wait_url": f"{PUBLIC_URL}/wait",
        "wait_time": MAX_WAIT_SECONDS,
        "transfer_after_bridge": "false",
    })
    # Reached only if the wait ran out.
    service.add_verb("play", {"url": "say:Sorry, no one could take your call. Goodbye."})
    service.add_verb("hangup", {})
    return service


def build_wait(service=None):
    service = service or SWMLService(name="queue-wait", route="/wait")
    service.reset_document()
    service.add_verb("play", {"url": HOLD_MUSIC})
    return service


def build_agent(service=None):
    service = service or SWMLService(name="queue-agent", route="/agent")
    service.reset_document()
    service.add_verb("answer", {})
    service.add_verb("connect", {"to": f"queue:{QUEUE}"})
    service.add_verb("hangup", {})
    return service


@app.route("/caller", methods=["GET", "POST"])
def caller():
    return jsonify(build_caller().get_document())


@app.route("/wait", methods=["GET", "POST"])
def wait():
    return jsonify(build_wait().get_document())


@app.route("/agent", methods=["GET", "POST"])
def agent():
    return jsonify(build_agent().get_document())


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
