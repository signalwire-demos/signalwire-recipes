# Collect speech input and branch

> The caller says what they want and the document routes them, with no agent
> in the path.

**Scenario:** a three-way front door for a small software company

## What this demonstrates

A menu the caller talks to instead of pressing. A recogniser turns the
utterance into a word, a `switch` picks the section, and the call is
transferred. There is no `ai` verb, no prompt to write and no model in the
path.

Speech input is not the same thing as an AI agent. This is the cheap version:
fixed vocabulary, deterministic routing, and nothing to govern.

## How it works

`prompt` plays a question and waits. What it listens for is decided by which
parameters you set, and the schema is precise about it. Speech detection is off unless
a speech parameter is present. Digit detection is off if only speech parameters are
present.

```yaml
- prompt:
    play: "say:Are you calling about sales, support, or your account?"
    speech_timeout: 12
    speech_end_timeout: 1.5
    speech_language: en-US
    speech_hints: [sales, support, account, billing]
```

No `max_digits`, so the keypad is never armed. Setting one would arm both.

`speech_hints` is the vocabulary. The recogniser is told what it is likely to
hear, which is the difference between matching "billing" and matching "Bill
Ng".

The branch reads `prompt_value`, which holds what the caller said.
`prompt_result` is a different variable, carrying the status of the attempt: values
like `match_speech` or `no_input`. Branch on the status instead of the content and the
menu stops working.

```yaml
- switch:
    variable: prompt_value
    case:
      sales:   [{ transfer: { dest: sales } }]
      account: [{ transfer: { dest: billing } }]
```

Two phrases can share a destination. "Account" and "billing" both reach the billing team. That is why the Python surface
keeps a table and builds the cases from it, rather than repeating YAML.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env
python app.py
```

Point a phone number's SWML webhook at `https://<your-host>/menu`. The SWML
surface can be pasted into a hosted SWML Script instead.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SWML schema. The verifier asserts:

- the verbs open `answer`, `prompt`, `switch`, and no section contains an `ai`
  verb
- the prompt sets speech parameters and no digit parameters
- the switch reads `prompt_value`, not `prompt_result`
- every case and the default target a section that exists
- every hint given to the recogniser is a phrase the switch can act on
- two phrases share the billing destination, and three destinations remain

## Limitations

The vocabulary is fixed. A caller who says "I need to pay my invoice" matches nothing
and is asked again. That is what you give up by having no model in the path.

Recognition is not exact. A hint improves the odds and does not guarantee them,
so the `default` branch is load bearing rather than decorative.

## What to change first

Add `max_digits: 1` to the prompt and a `"1"` case beside `sales`. Both detectors arm,
and the same `switch` serves both, because a digit arrives in `prompt_value` exactly
as a word does. Add the digit without the case and every keypress falls to the
default.
