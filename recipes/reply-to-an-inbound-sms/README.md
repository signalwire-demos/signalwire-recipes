# Reply to an inbound SMS

> An inbound message hits your handler and a reply goes back on the same number, with keyword branching and media download.

**Scenario:** a business number that answers HOURS, HELP and STOP by text

## What this demonstrates

Inbound messaging is a webhook that returns a *messaging* SWML document. The
`reply` verb answers the sender on the number they texted; an inline `switch`
branches the body on a keyword with no server at all. The Python surface does
the same branching in code and shows where MMS attachments arrive.

## How it works

Markup only: the whole handler is one document.

```yaml
- reply:
    switch:
      variable: message.body
      transform: lowercase_trim
      case:
        hours: "We are open Monday to Friday, nine to five, Eastern time."
        help:  "Text HOURS for opening hours, or STOP to unsubscribe."
        stop:  "You have been unsubscribed and will receive no more messages."
      default: "Thanks for your message. A person will reply shortly."
```

Python: SignalWire POSTs the documented inbound-message payload
(`message.from`, `message.to`, `message.body`, `message.media[]` with `url`
and `content_type`) and executes whatever document the handler returns:

```json
{"version": "1.0.0", "sections": {"main": [{"reply": {"body": "..."}}]}}
```

Attachments on an MMS are URLs in `message.media`; download them from the
handler. `reply` can also attach `media` to answer with an MMS, and takes a
`status_url` for delivery callbacks (see `send-an-sms` for handling those).

**STOP is your job.** SignalWire does not manage opt-outs; the handler records
the sender so nothing is sent to them later. The full pattern is
`handle-opt-outs-yourself`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script and assign it as a
phone number's *message* handler.

Python:

```bash
cd python
pip install -r requirements.txt
python app.py
```

Set the number's message handler to `https://<your-host>/sms`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

It drives the webhook with the documented payload and asserts:

- the returned document is a `reply` whose body follows the keyword
- a media-only MMS records the attachment URL
- STOP is recorded
- the YAML switch covers the same keywords

## What to change first

Replace the static replies with `run-the-same-agent-over-text`: forward the
body to the AI Chat API and reply with the agent's answer.
