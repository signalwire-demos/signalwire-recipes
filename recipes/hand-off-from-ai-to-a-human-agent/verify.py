"""Prove the claim without a network.

Claim: the agent's tool writes its notes under the call's id and hands the
call to a named queue with `enter_queue`. The human's side reads the next queue
member over REST, whose documented fields include that same `call_id`, and
finds the notes by it. The human takes the call with `connect` to
`queue:<name>`.

Proof: execute the tool offline with a tool webhook body that carries
`call_id` and `caller_id_num`. The result is one SWML action with exactly one
`enter_queue` verb, `transfer` set to "true", and the document validates. The
notes sit under that call id with the caller's name, issue and number. With
the HTTP layer replaced by a recorder that answers the queue list and the next
member, `brief` makes one GET of the next member for the configured queue id
and returns the notes for the member's `call_id`. The bundled schema requires
`queue_name` and `transfer_after_bridge` on `enter_queue` and lists the
`queue:` form for `connect.to`; the spec documents `call_id` on a queue member.
The human's document validates and connects to `queue:support`. Expected values
live here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "QUEUE_NAME": "support",
    "QUEUE_ID": "4d5e6f70-8192-4a3b-9c4d-5e6f708192a3",
    "NOTES_PATH": str(HERE / "python" / ".verify-notes.json"),
})

import verifylib as V  # noqa: E402

QUEUES = "/api/relay/rest/queues"
QID = "4d5e6f70-8192-4a3b-9c4d-5e6f708192a3"
CALL = "c-7f1e2d3c-4b5a-4968-8776-5544332211aa"
NOTE = {"caller_name": "Dana", "issue": "the rear brake rubs after the service on Monday",
        "from": "+15550002222"}


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    from app import agent, take
    import app as recipe

    notes_file = pathlib.Path(os.environ["NOTES_PATH"])
    notes_file.unlink(missing_ok=True)  # start from no notes, as a fresh clone does
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["function"] == "hand_off" and fn["parameters"]["required"] == ["caller_name", "issue"], fn

    # the tool: notes under the call id, then one enter_queue with transfer
    raw = {"call_id": CALL, "caller_id_num": "+15550002222", "argument": {"parsed": [{}]}}
    got = agent._execute_swaig_function(
        "hand_off", {"caller_name": "Dana", "issue": NOTE["issue"]}, call_id=CALL, raw_data=raw)
    assert got["response"] == "Thanks. I am putting you through to a person now.", got
    (action,) = got["action"]
    assert set(action) == {"SWML", "transfer"} and action["transfer"] == "true", action
    V.validate_swml(action["SWML"])
    assert V.verb_names(action["SWML"]) == ["enter_queue"], V.verb_names(action["SWML"])
    assert V.first(action["SWML"], "enter_queue") == {"queue_name": "support",
                                                       "transfer_after_bridge": "false"}
    # the notes are on disk, where a second process can read them
    assert json.loads(notes_file.read_text(encoding="utf-8")) == {CALL: NOTE}

    # the human's side: the next member's call_id is the key
    rec = V.Recorder(responses=[
        {"call_id": CALL, "queue_id": QID, "position": 1, "wait_time": 42},
    ])
    import importlib
    recipe = importlib.reload(recipe)  # a second interpreter, as far as NOTES go
    recipe.client.queues._http = rec
    screen = recipe.brief()            # the queue id comes from QUEUE_ID
    assert screen == {"call_id": CALL, "position": 1, "waiting_seconds": 42, "notes": NOTE}, screen
    assert [(c["method"], c["path"]) for c in rec.calls] == \
        [("GET", f"{QUEUES}/{QID}/members/next")], rec.calls
    assert all(c["params"] is None and c["body"] is None for c in rec.calls), rec.calls
    spec = V.spec("rest")
    V.assert_documented("rest", "GET", QUEUES, None)
    V.assert_documented("rest", "GET", f"{QUEUES}/{{queue_id}}/members/next", None)
    op = spec["paths"][f"{QUEUES}/{{queue_id}}/members/next"]["get"]
    member = deref(spec, op["responses"]["200"]["content"]["application/json"]["schema"])
    assert {"call_id", "position", "wait_time"} <= set(member["properties"]), sorted(member["properties"])
    assert "without dequeuing" in op["description"], op["description"]
    queue_item = deref(spec, deref(spec, deref(spec, spec["paths"][QUEUES]["get"]["responses"]["200"]
                                       ["content"]["application/json"]["schema"])["properties"]["data"])["items"])
    assert "friendly_name" in queue_item["properties"], sorted(queue_item["properties"])

    # the human's document, and the schema's word on both verbs
    human = take().get_document()
    V.validate_swml(human)
    assert V.verb_names(human) == ["answer", "connect"], V.verb_names(human)
    assert V.first(human, "connect") == {"to": "queue:support"}, V.first(human, "connect")
    defs = V.swml_schema()["$defs"]
    assert defs["EnterQueueObject"]["required"] == ["queue_name", "transfer_after_bridge"]
    assert "queue:" in defs["ConnectDeviceSingle"]["properties"]["to"]["description"]

    notes_file.unlink(missing_ok=True)
    print(f"ok: hand_off stores notes under {CALL[:10]}... and returns one enter_queue(support) "
          f"with transfer; the next queue member carries that call_id and brief() finds the notes; "
          f"the human connects to queue:support")


if __name__ == "__main__":
    main()
