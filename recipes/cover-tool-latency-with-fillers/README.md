# Cover AI agent tool latency with fillers

> The slow tool renders a filler phrase, and a wait file when you host one. Each language carries its own filler pool.

**Scenario:** a parts desk checking a slow inventory system

## What this demonstrates

While a tool runs, the model is not running, so nothing in your prompt can cover
the gap. Three fields on the document do. `fillers` on the function is a phrase for
the moment this tool is called. `wait_file` is audio the platform loops while the
tool is still running, and this recipe renders it only when you host a file.
`function_fillers` on each language entry is the pool the platform draws from for
any tool, in that language.

Docs: [SWAIG functions](https://signalwire.com/docs/swml/reference/calling/ai/swaig/functions)
and [multilingual](https://signalwire.com/docs/swml/reference/calling/ai/multilingual).

## How it works

The function carries its own filler and, when `WAIT_FILE_URL` is set, its wait
file.

```python
@AgentBase.tool(
    name="check_stock",
    description="Look up how many of a part are in stock by its SKU.",
    parameters={...},
    fillers={"en-US": ["Checking the warehouse now."]},
    wait_file="https://cdn.example.com/audio/hold.mp3",
    wait_file_loops=3,
)
```

The function-level `fillers` dict takes one language key. The 3.0.1 schema defines
it as one-of-one-language, and the schema rejects a dict with two keys. Your
per-language pools go on the languages.

```python
self.add_language("Spanish", "es-ES", "rime.spore",
                  speech_fillers=["Vale."],
                  function_fillers=["Un momento, estoy comprobando."])
self.set_params({"languages_enabled": True})
```

Pass both `speech_fillers` and `function_fillers`. With only one, the SDK writes
the deprecated single `fillers` key on the language, and the verifier shows it.
Set `languages_enabled`, or the platform ignores the list.

The app does not host audio. You attach `wait_file` by setting `WAIT_FILE_URL`
to a file the platform can fetch; with it unset, the function renders without
either wait key.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD and WAIT_FILE_URL
LOOKUP_DELAY_SECONDS=3 python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/stock/` and ask for part SK-2210. The delay
lets you hear the gap being covered. Set it back to 0 afterwards.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML with and without a wait file URL, validates both, and asserts
the following.

- `check_stock` carries the exact `fillers` phrase, the wait file URL unchanged, and `wait_file_loops`
- with no `WAIT_FILE_URL`, neither wait file key is present
- a language given only `speech_fillers` renders the deprecated `fillers` key instead
- both languages carry the exact `speech_fillers` and `function_fillers` arrays, and no deprecated `fillers` key
- `languages_enabled` is on
- the schema rejects a two-language `fillers` dict on the function

## Limitations

Fillers cover latency; they do not shorten it. Keep `wait_file_loops` low so the
returning silence tells you something is wrong.

The verifier proves what the document says, not what a caller hears. The linked
platform docs describe which phrase plays and when.

## What to change first

Empty `WAIT_FILE_URL` and run the verifier. The `wait_file` keys disappear from the
rendered function, which is the difference between promising audio and playing it.
