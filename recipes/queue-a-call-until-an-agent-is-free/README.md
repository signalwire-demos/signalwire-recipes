# Queue a call until an agent is free

> Callers wait in a named queue with hold audio and are bridged in order as agents connect to it.

**Scenario:** a support line where callers hold for the next available person

## What this demonstrates

Queues are native. A caller enters a named queue with `enter_queue`; an agent
takes the next waiting caller with `connect: { to: "queue:<name>" }`. The
platform keeps the order, plays the hold document, and bounds the wait. No
queue service of your own, no polling.

## How it works

Three small documents:

```yaml
main:                                  # what a caller runs
  - answer: {}
  - enter_queue:
      queue_name: support
      wait_url: "https://<your-host>/wait"   # re-run while the caller waits
      wait_time: 600                         # seconds before giving up
      transfer_after_bridge: "false"
  - play: { url: "say:Sorry, no one could take your call. Goodbye." }   # fall-through
wait:                                  # served at wait_url
  - play: { url: "https://.../hold-music.mp3" }
agent:                                 # what an agent dials
  - answer: {}
  - connect: { to: "queue:support" }
```

The verbs after `enter_queue` run only if `wait_time` expires with nobody
answering, and that is where you offer a callback instead
(`offer-a-callback-instead-of-a-hold`). Queue depth and the next member are also
readable over REST (`/api/relay/rest/queues`), and the Compatibility API has the
same shape as `<Enqueue>` / `<Dial><Queue>`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script. Assign one number to
the `main` section (callers) and another to the `agent` section (agents); host
the `wait` section at `wait_url`.

Python:

```bash
cd python
pip install -r requirements.txt
PUBLIC_URL=https://<your-host> QUEUE_NAME=support python app.py
```

Point the callers' number at `https://<your-host>/caller` and the agents'
number at `https://<your-host>/agent`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

All three documents validate against the SWML schema. The verifier asserts the queue
name, a `wait_url`, a bounded `wait_time`, the fall-through after `enter_queue`, and
that the agent document connects to `queue:support`.

## What to change first

Lower `wait_time` and put an `offer-a-callback-instead-of-a-hold` flow in the
fall-through, so nobody waits more than a few minutes without being offered a
way out.
