"""Hand off from AI to a human agent.

Two halves and one key. The agent's `hand_off` tool writes what it learned
under the call's id, then returns a SWML action whose one verb is
`enter_queue`. The bundled schema requires `queue_name` and
`transfer_after_bridge` on it. It describes the verb as placing the call in a
named queue "where it will wait to be connected to an available agent or
resource". The human's side asks the vendored REST spec's
`GET /api/relay/rest/queues/{queue_id}/members/next` for the next member.
Its documented fields include `call_id`, and the notes are looked up by it.
The human takes the call with a `connect` whose `to` is `queue:<name>`, a form
the bundled schema lists for `connect.to`.

The call id is the join. The SWAIG tool webhook carries it as `call_id`, the
queue member carries it as `call_id`, and nothing else has to agree.

Written against signalwire-sdk 3.0.1 (AgentBase, FunctionResult,
RestClient.queues, SWMLService).
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult, SWMLService
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

QUEUE = os.getenv("QUEUE_NAME", "support")
# the queue's id, for the human's screen: the REST list of queues carries it
QUEUE_ID = os.getenv("QUEUE_ID")

# call_id -> what the agent learned before it handed off. The agent and the
# human's screen are two processes (python app.py, then python app.py brief),
# so the notes live in a file both can open; swap the two functions for your
# database. A dictionary here would be empty in the second process.
NOTES_PATH = Path(os.getenv("NOTES_PATH", "handoff-notes.json"))


def save_note(call_id, note):
    notes = load_notes()
    notes[call_id] = note
    # write whole, then swap in: a reader never sees a half-written file
    tmp = NOTES_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes, indent=2), encoding="utf-8")
    os.replace(tmp, NOTES_PATH)


def load_notes():
    if not NOTES_PATH.exists():
        return {}
    return json.loads(NOTES_PATH.read_text(encoding="utf-8"))

# enter_queue: the caller waits here; "false" means carry on in this document
# after the bridge, and there is nothing after it, so the call ends with the bridge
ENQUEUE = {"version": "1.0.0", "sections": {"main": [
    {"enter_queue": {"queue_name": QUEUE, "transfer_after_bridge": "false"}}]}}


class TriageAgent(AgentBase):
    def __init__(self):
        super().__init__(name="triage", route="/triage")
        self.prompt_add_section(
            "Role",
            "You are the front desk at Ridgeline Cycles. Find out who is calling and "
            "what the problem is in one or two questions. When you have both, or when "
            "the caller asks for a person, call hand_off with what you learned.")

    @AgentBase.tool(
        name="hand_off",
        description=("Hand the caller to a person, with a short note of who they are "
                     "and why they called."),
        parameters={
            "type": "object",
            "properties": {
                "caller_name": {"type": "string",
                                "description": "The caller's name as they gave it."},
                "issue": {"type": "string",
                          "description": "One sentence on why they called."},
            },
            "required": ["caller_name", "issue"],
        },
    )
    def hand_off(self, args, raw_data):
        call_id = raw_data["call_id"]
        save_note(call_id, {
            "caller_name": args["caller_name"],
            "issue": args["issue"],
            "from": raw_data.get("caller_id_num"),
        })
        result = FunctionResult("Thanks. I am putting you through to a person now.")
        # the documented action: the SWML, and a sibling transfer flag so the
        # call leaves the agent for the queue (execute_swml(transfer=True) puts
        # the flag inside the document instead)
        result.action.append({"SWML": ENQUEUE, "transfer": "true"})
        return result


def brief(queue_id=None):
    """What the human's screen shows: the next caller and the agent's notes."""
    queue_id = queue_id or QUEUE_ID
    if not queue_id:
        raise SystemExit("QUEUE_ID is required for brief; see .env.example")
    member = client.queues.get_next_member(queue_id)
    call_id = member["call_id"]
    return {"call_id": call_id, "position": member.get("position"),
            "waiting_seconds": member.get("wait_time"),
            "notes": load_notes().get(call_id)}


def take(service=None):
    """The document the human's phone runs to answer the front of the queue."""
    service = service or SWMLService(name="take", route="/take")
    service.add_verb("answer", {})
    service.add_verb("connect", {"to": f"queue:{QUEUE}"})
    return service


agent = TriageAgent()

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "brief":
        print(json.dumps(brief(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == "take":
        # the human's document, served behind the same basic-auth pair
        take().serve(port=int(os.getenv("TAKE_PORT", "3001")))
    else:
        agent.run()
