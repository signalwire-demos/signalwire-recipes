# Control when a caller can interrupt a voice AI agent

> Whether a caller can cut the agent off, how many words it takes, whether the greeting plays through, and how much silence ends the caller's turn are ten keys in `ai.params`. The schema bounds each one, and the rendered document carries exactly those keys.

**Scenario:** a bike shop's front desk that finishes its greeting and lets a caller cut in after a few words

## What this demonstrates

Interruption is not a prompt problem. "Let the caller interrupt you" in the
prompt does nothing to the audio pipeline; `enable_barge` does. This agent sets
the turn-taking parameters the `ai.params` reference documents, from
configuration. The verifier proves the document carries exactly them.

Four groups of settings. `enable_barge`, `barge_min_words`, `transparent_barge`
and `interrupt_on_noise` say when the caller's speech stops the agent.
`static_greeting` and `static_greeting_no_barge` keep the opening line whole.
`end_of_speech_timeout`, `first_word_timeout` and `speech_event_timeout` decide
when the caller has finished. `energy_level` and `enable_turn_detection` tune
what counts as speech at all.

The greeting is the trap in that group. `static_greeting_no_barge` protects
`ai.params.static_greeting`, the line the platform speaks before the model
does. A prompt section telling the model to open with a greeting produces
generated speech instead. That setting does not cover it, so the opening line
has to be a param.

## How it works

```python
TURN_TAKING = {
    "static_greeting": GREETING,              # what the platform speaks first
    "enable_barge": barge_value(...),         # string or boolean; false is off
    "barge_min_words": 3,                     # 1-99
    "transparent_barge": True,                # do not answer speech-over
    "interrupt_on_noise": False,              # a cough is not an interruption
    "static_greeting_no_barge": True,         # the greeting plays through
    "end_of_speech_timeout": 700,             # ms of silence, 250-10000
    "first_word_timeout": 1000,               # ms, 0-10000
    "speech_event_timeout": 1400,             # ms, 0-10000
    "energy_level": 52,                       # dB, 0.0-100.0
    "enable_turn_detection": True,            # punctuation ends the turn
}

class FrontDesk(AgentBase):
    def __init__(self, turn_taking=None):
        super().__init__(name="front-desk", route="/front-desk")
        self.prompt_add_section("Role", ...)   # no greeting section: see above
        self.set_params(TURN_TAKING if turn_taking is None else turn_taking)
```

The [params reference](https://signalwire.com/docs/swml/reference/calling/ai/params.md)
describes `enable_barge` as "Controls when user can interrupt the AI". Its
values are `complete`, `partial`, `all` or a boolean, and `false` is how you
turn barging off. `barge_min_words` is "the number of words that must be input
before triggering barge behavior". `static_greeting_no_barge` keeps the static
greeting from being interrupted "if they speak over the greeting".
`end_of_speech_timeout` is "Amount of silence, in ms, at the end of an
utterance to detect end of speech". `static_greeting` is "The static greeting
to play when the call is answered", which "will always play at the beginning of
the call".

The bundled schema turns those into bounds: `barge_min_words` 1 to 99,
`end_of_speech_timeout` 250 to 10,000, `first_word_timeout` and
`speech_event_timeout` 0 to 10,000, `energy_level` 0.0 to 100.0. It states a
default for eight of the ten, and none for `barge_min_words` or
`interrupt_on_noise`.

Two traps. `AIParams` accepts keys it does not know, so `enable_barg` renders,
validates and does nothing; the verifier asserts the exact key set rather than
only that the document validates. And an environment variable is always a
string, so `ENABLE_BARGE=false` would reach the document as the word "false",
which the reference does not list. The parser turns it into the boolean, and
turns a whole `ENERGY_LEVEL` into an integer so both surfaces render the same
number. A value that is not an integer where the schema wants one stops the
process instead of shipping a document the platform refuses.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # basic auth; every turn-taking key has a value
python app.py                    # serves /front-desk/
```

The TypeScript surface is the same agent with `setParams`, on Node 20.18.1 or
newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start
```

Point a number at `https://<user>:<password>@<your-host>/front-desk/` and talk
over the greeting: it finishes, because it is a static greeting. Then interrupt an answer with one word, and
with four.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

With `BARGE_MIN_WORDS` set to four so one value is off its default, the
verifier renders the document and asserts the following.

- `ai.params` equals the eleven configured keys and values, nothing more, and the document validates
- the greeting is `static_greeting`, and the rendered prompt does not carry it, so the protected line is the one the platform speaks
- the schema's bounds are what this README states, read from the bundled schema rather than remembered, and so are its eight defaults
- `barge_min_words` and `interrupt_on_noise` carry no default in the schema, which is why this README does not claim one for them
- `barge_min_words: 100` and `end_of_speech_timeout: 249` fail validation, one step outside the bound; 99 and 250 pass
- `energy_level: 52.5` validates, because the schema types it as a number
- `enable_barge: false` validates, and the schema takes a string or a boolean there
- a document with the misspelt key `enable_barg` validates, which is why the exact-key check is the guard
- `ENABLE_BARGE=false`, in any casing or spacing, parses to the boolean; `true` parses to `true`; a listed word stays a string
- `ENERGY_LEVEL=52.5` parses to a float and `52` to an integer, so the two surfaces render the same document
- an empty integer setting falls back to the default, while a non-numeric or fractional one raises
- the TypeScript surface renders the same eleven params, the same six variants and the same parses

## Limitations

The verifier proves the document, not the conversation. How a given value
feels on a call is a call to make, and the read-back in this recipe's
*Run it* is the test.

The reference types `interrupt_on_noise` as a boolean or a positive integer
threshold. The bundled 3.0.1 schema takes the boolean only, so an integer
there fails `validate_swml` offline even though the page allows it.

`vad_config`, `barge_match_string` and `barge_functions` are on the same
object and left at their defaults here. Changing turn-taking mid-call is a
different mechanism: `set_end_of_speech_timeout` is an action on a tool
result, not an `ai.params` key, so it is out of this claim.

## What to change first

Set `ENABLE_BARGE=false` in `.env` and run the verifier. The expected value no
longer matches, which is the point. That one setting decides whether
interruption exists at all, and it has to reach the document as a boolean
rather than the word.
