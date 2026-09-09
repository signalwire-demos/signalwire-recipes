# Build an IVR menu

> Press-1 menus branch to different sections without a line of server code.

**Scenario:** a main line that routes to sales, support, or a recorded message

## What this demonstrates

A complete phone menu is one SWML document: `prompt` collects a digit, `switch`
branches on it, and each branch is a named section. Nothing here needs a server:
host the YAML as a SWML Script in the Dashboard and point a number at it.

The Python surface builds the identical document with `SWMLService`. Destinations come
from the environment, and every verb is validated against the SWML schema before it is
served.

## How it works

```yaml
- prompt:
    play: "say:Thanks for calling. Press 1 for sales, 2 for support, or 3 for opening hours."
    max_digits: 1
- switch:
    variable: prompt_value
    case:
      "1": [ { transfer: { dest: sales } } ]
      "2": [ { transfer: { dest: support } } ]
      "3": [ { transfer: { dest: hours } } ]
    default: [ { play: { url: "say:Sorry, I did not catch that." } }, { transfer: { dest: main } } ]
```

`prompt` stores the digit in `prompt_value`. `switch` matches it and `transfer`
jumps to a section of the same document. The `sales` and `support` sections
`connect` to a phone number; `hours` plays a message and hangs up. An
unrecognised key re-prompts by transferring back to `main`.

## Run it

Markup only: paste `swml/agent.yaml` into a new SWML Script in the Dashboard,
assign a phone number to it, call the number.

Python:

```bash
cd python
pip install -r requirements.txt
SALES_NUMBER=+1555... SUPPORT_NUMBER=+1555... python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/ivr/`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces are validated against the SDK's bundled SWML schema. The verifier
asserts:

- one digit is collected
- every case transfers to a section that exists
- the default branch re-prompts

## What to change first

Add a fourth option that transfers to a SIP address instead of a number.
Alternatively, collect speech with `speech_hints` and branch on what the caller says. See `collect-speech-input-and-branch`.
