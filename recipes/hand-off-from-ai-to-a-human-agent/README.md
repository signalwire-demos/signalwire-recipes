# Hand off from AI to a human agent

> The agent's tool writes its notes under the call's id and hands the call to a named queue with `enter_queue`. The human's side reads the next queue member over REST, whose documented fields include that same `call_id`, and finds the notes by it.

**Scenario:** a bike shop front desk that takes the name and the problem, then puts the caller through to a person who already knows both

## What this demonstrates

Three documented pieces, joined by one id. The SWAIG tool webhook, documented
in the REST spec as `ai-swaig-tool-webhook`, carries the call's `call_id`, so
the handler can key its notes by it. `enter_queue` puts the
caller in a named queue. The bundled schema requires `queue_name` and
`transfer_after_bridge` on it. It describes the verb as placing the call where
"it will wait to be connected to an available agent or resource". The vendored REST
spec's `GET /api/relay/rest/queues/{queue_id}/members/next` "Retrieves the next
member in the queue without dequeuing", and the member carries `call_id`,
`position` and `wait_time`. The human takes the call with a `connect` whose `to`
is `queue:support`, one of the forms the schema lists for `connect.to`.

## How it works

```python
def hand_off(self, args, raw_data):
    call_id = raw_data["call_id"]
    save_note(call_id, {"caller_name": args["caller_name"], "issue": args["issue"],
                        "from": raw_data.get("caller_id_num")})
    result = FunctionResult("Thanks. I am putting you through to a person now.")
    result.action.append({"SWML": ENQUEUE, "transfer": "true"})   # the documented shape
    return result

def brief(queue_id):
    member = client.queues.get_next_member(queue_id)
    return {"call_id": member["call_id"], ..., "notes": load_notes().get(member["call_id"])}
```

What the platform receives from the tool, then what the human's phone runs:

```json
{"response": "Thanks. I am putting you through to a person now.",
 "action": [{"SWML": {"version": "1.0.0", "sections": {"main": [
               {"enter_queue": {"queue_name": "support", "transfer_after_bridge": "false"}}]}},
             "transfer": "true"}]}

{"version": "1.0.0", "sections": {"main": [{"answer": {}}, {"connect": {"to": "queue:support"}}]}}
```

`transfer_after_bridge` is a string the schema requires; `"false"` means carry
on in this document after the bridge, and there is nothing after it. The
`transfer: "true"` beside the SWML is what the tool webhook documents for a
call that leaves the agent. `FunctionResult.execute_swml(transfer=True)` would
put that flag inside the document, so the action is built by hand. The notes
go to a JSON file at `NOTES_PATH`. The agent and the screen are two processes,
so a dictionary in the agent would be empty in the shell that runs `brief`.
Swap the two functions for your database. The screen asks for the next member,
takes its `call_id`, and shows the notes filed under it.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, the basic-auth pair, QUEUE_NAME, QUEUE_ID
python app.py                    # the agent, on port 3000
python app.py take               # in another shell: the human's document, on port 3001
python app.py brief              # in a third: who is next, and what the agent learned
```

`QUEUE_ID` is the id of the queue named in `QUEUE_NAME`. `enter_queue` creates
the queue by name on first use, and `GET /api/relay/rest/queues` lists it with
its id. Point the human's number at the `take` document, behind the same
basic-auth pair.

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point the shop's number at
`https://<user>:<password>@<your-host>/triage/`. The schema says a queue that
does not exist is created on first use, so the first hand-off creates
`support`. The `take` command serves the human's document on port 3001, behind
the same basic-auth pair. Expose it the same way and point the human's number
at it. When the human dials in, the platform bridges the front of the queue.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier executes the tool offline, swaps the SDK's HTTP layer for a
recorder, and asserts the following.

- the rendered agent has one function, `hand_off`, requiring `caller_name` and `issue`
- executing it with a tool webhook body that carries `call_id` and `caller_id_num` returns the exact response and one action
- that action's SWML validates, holds exactly one `enter_queue` with `queue_name: support` and `transfer_after_bridge: "false"`, and carries `transfer: "true"`
- the notes sit under the call id with the name, the issue and the number, and nothing else
- the notes land in the file at `NOTES_PATH`, and `brief`, run after the module is reloaded as a second process would load it, reads them back from there
- `brief` makes one `GET` of the documented next-member path for the configured `QUEUE_ID`, with no body or query, and returns the member's position, wait and the notes for its `call_id`
- the spec documents `call_id`, `position` and `wait_time` on the member and describes the read as "without dequeuing"
- the human's document validates and connects to `queue:support`; the schema requires `queue_name` and `transfer_after_bridge` and lists the `queue:` form for `connect.to`

## Limitations

You prove the documents, the tool result and the requests. Who the platform
bridges to whom, and how long the caller waits, are the platform's side of a
live call. The next-member read does not dequeue; the bridge does. The two are
not one step. Between the read and the bridge the front of the queue can
change, and the screen would then describe a different caller than the one
bridged. Correlate by `call_id` on the bridged call before you act on the notes.

The notes are a local JSON file the two processes share, written whole and
swapped in. It is not a store for concurrent hand-offs or for production; put
them in a database keyed by `call_id` before anything depends on it.

## What to change first

Key the note by `args["caller_name"]` instead of `call_id` and run the verifier.
The `brief` assertion fails, because the queue member carries a call id and no
name. The id is the only field both sides hold.
