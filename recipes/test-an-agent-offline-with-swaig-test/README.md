# Test a voice AI agent offline with swaig-test

> The SDK's `swaig-test` command loads an agent file with no number, tunnel or account. It prints the SWML the platform would fetch, lists the tools, and runs any tool with the arguments you give it.

**Scenario:** checking a shop-hours agent before it ever answers a call

## What this demonstrates

`swaig-test` is a console script the SDK installs alongside itself. Its entry
point is `signalwire.cli.swaig_test_wrapper:main`, and `signalwire/cli/test_swaig.py`
is the implementation. It imports your agent file, finds the `AgentBase` in it,
and lets you inspect three things before any call.
`--dump-swml --raw` prints the exact document the platform would fetch.
`--list-tools` prints every tool with its parameters. `--exec <tool> --<arg>
value` runs the handler with fake call data and prints the `FunctionResult`.

Nothing in the agent knows about the CLI. It is the same file you would serve.

## How it works

```bash
swaig-test python/app.py --dump-swml --raw       # the document, as JSON
swaig-test python/app.py --list-tools            # check_hours and its 'day' parameter
swaig-test python/app.py --exec check_hours --day saturday
```

The last command prints the handler's result:

```
RESULT:
FunctionResult: On Saturday the shop is open 9 to 5.
```

Every `--<name> value` after `--exec <tool>` becomes an argument to the tool,
so the same handler code that will run on a call runs here. Flags such as
`--from-number`, `--call-direction` and `--user-vars` shape the fake call data;
`--custom-data` sets `global_data`; `--simulate-serverless` runs the agent as
a Lambda, Cloud Function, Azure Function or CGI handler would.

The verifier does not use the installed script. It runs the same entry point as
a subprocess, `python -m signalwire.cli.swaig_test_wrapper`, so it proves the
CLI against the SDK it loaded.

## Run it

Run the verifier first (below): it refuses to run once a `.env` exists.

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
swaig-test app.py --list-tools
swaig-test app.py --exec check_hours --day thursday
python app.py                    # when you are ready to serve it for real
```

Importing `app.py` runs its `load_dotenv()`, so the basic-auth pair in `.env`
reaches the agent the same way it does when you serve it.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

The verifier runs the CLI as a subprocess against `python/app.py`, four times,
and asserts the following.

- `--dump-swml --raw` prints JSON that validates against the bundled schema and carries exactly one tool, `check_hours`
- `--list-tools` prints the tool's block: its description line, `Parameters:`, then `day (string) (required)` with its description, and no second tool
- `--exec check_hours --day saturday` prints `RESULT:` and then the handler's exact response on the `FunctionResult:` line
- `--exec check_hours --day someday` prints the handler's `INVALID` refusal the same way
- the child process gets an environment with only the SDK path and a fixed verifier-only basic-auth pair, so no account credential is in reach
- the verifier refuses to run if a `.env` exists anywhere `load_dotenv()` searches: `python/`, the recipe folder, or a parent

## Limitations

`swaig-test` runs your handler; it does not run the model. It cannot tell you
whether the model would choose `check_hours` for a given sentence.

The CLI is Python-only. A SWML-only recipe has nothing for it to load; validate
those documents with the schema instead.

## What to change first

Change `"saturday": "9 to 5"` to `"9 to 4"` in `HOURS` and run the verifier. The
`--exec` assertion fails with the new text, which is the point: the CLI ran the
handler you edited a moment ago, before any call did.
