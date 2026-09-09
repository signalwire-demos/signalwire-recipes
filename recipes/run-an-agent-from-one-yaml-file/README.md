# Run a voice AI agent from one YAML file

> A complete agent in one document, with nothing to deploy.

**Scenario:** a 40 seat restaurant taking reservations

## What this demonstrates

An AI agent that is a file. Paste it into a SWML Script in the Dashboard and point a
number at it, and the platform hosts and runs it. No SDK, and no server of yours in
the path of the call. Nothing has to be online for the agent to answer and hold a
conversation.

The document does name one URL, and it is worth being exact about what that buys.
`post_prompt_url` receives a report after the call ends. Nothing is served from it, so
the agent runs whether or not it answers.

## How it works

The `ai` verb carries the whole agent. `prompt.text` is the identity, written in
markdown because the model reads structure better than a paragraph.

```yaml
- ai:
    prompt:
      text: |
        ## Role
        You take reservations for Ridgeline Kitchen, a 40 seat restaurant.
        ## Boundaries
        The kitchen seats parties up to 8. For anything larger, take a
        phone number and say the manager will call back.
    post_prompt:
      text: >-
        Return only JSON with the keys name, party_size, requested_time
        and outcome.
    post_prompt_url: "https://your-host.example.com/reservation"
```

`post_prompt` runs after the call and POSTs its result to `post_prompt_url`. That is a
callback, so something of yours does have to receive it if you want the reservation.
Delete both fields and the agent still answers calls, with nowhere to report what
happened.

`params` bounds the call. `inactivity_timeout` and `attention_timeout` stop an abandoned call holding a line
open. They matter more here than in a supervised agent, because no code is watching.

`hints` tells the recogniser the words it would otherwise guess at. A proper
noun like a restaurant's name is the usual case.

This document has no tool, which is a choice rather than a limit. A tool with a
handler needs a webhook, and a webhook is a server. A DataMap tool does not: it
carries its request in the document, so an agent that only reads a third-party API
stays serverless. That is `call-an-api-without-a-backend`. The moment a tool needs
code of yours to decide something, this recipe stops being the right shape and
`give-an-agent-a-tool` starts.

## Run it

There is nothing to run locally. In the Dashboard, create a SWML Script,
paste `swml/agent.yaml`, and set a phone number's handler to that script.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

The document validates against the SDK's bundled SWML schema. The verifier
asserts:

- the verbs are `answer`, `ai`, `hangup`
- the agent has both a prompt and a post-prompt with a destination
- there is no `SWAIG` block at all, so no tool needs a handler of yours
- the post-prompt URL is the only URL in the agent, and it is a sink
- both timeouts are set, so an abandoned call ends
- the recogniser is given the proper noun as a hint

## Limitations

No tools means no lookups, no bookings written anywhere, and no validation. The
agent can take a reservation and tell you about it afterwards; it cannot check
whether the table is free.

Editing means editing the document. There is no version control, no test and no
review unless you keep the file somewhere that has them.

## What to change first

Lower `attention_timeout` to two seconds and call it. The agent starts prompting
over a caller who is only thinking, which is what that parameter buys.
