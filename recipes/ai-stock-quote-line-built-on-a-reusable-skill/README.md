# AI stock quote line: two agents sharing one reusable skill with different settings

> A stock quote demo built to show a skill written once and loaded by two agents with different parameters. The skill holds the provider, keeps the API key out of the SWML, and scopes each agent by a watchlist.

**Scenario:** A caller asks what a ticker is trading at; a public line answers any symbol and an employee line answers only the company's

## What this demonstrates

A reusable skill instead of a one-off tool. `skills/stock_quote/skill.py` is a
`SkillBase` subclass. It declares its parameters (`get_parameter_schema`),
checks them in `setup()`, registers its tool, and brings its own prompt
section, speech hints and fillers. An agent gets all of that with one
`add_skill("stock_quote", {...})` call. The skill, not the prompt, holds the
rules every agent inherits. The provider and key stay in code, each agent's
scope is a parameter, and failures are spoken rather than raised.

A caller asks "What's Acme trading at?" and hears the price and today's change
in a sentence that reads well aloud. One process serves two agents. A public
quote line at `/` loads the skill with a provider and key and answers any
ticker through `get_stock_quote`. An employee stock-plan line at `/stock-plan`
loads the same skill with `tool_name="get_company_share_price"` and
`watchlist=["ACME"]`, so it answers one ticker only. By default quotes come
from a bundled mock feed with fictional tickers, so a clean clone needs no
market-data account.

## How it works

`api_key` is marked `hidden` and never appears in the SWML (a test checks
that), so no model or caller can read it. A paid provider with no key fails at
`add_skill()` time, not halfway through a call. Finnhub gets the key in the
`X-Finnhub-Token` header. Alpha Vantage only accepts it in the query string,
so a failed request logs the error type and HTTP status, never the URL.
`SUPPORTS_MULTIPLE_INSTANCES = True` lets each agent name its own tool, so
each agent's SWML lists only its own. A bad ticker, an unknown symbol, a rate
limit or a timeout each come back as a sentence telling the model what to say
next.

Where each mechanism lives in the repository:

- the `SkillBase` subclass with `get_parameter_schema`, `setup` and `register_tools`: `skills/stock_quote/skill.py`
- `add_skill_directory`: `app.py`, module top
- `add_skill("stock_quote", params)` with different params: `app.py`, both agents
- `AgentServer` hosting two agents: `app.py`, `__main__`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a skill package. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The agents are stateless, so you can run as many replicas as you like. Real
quotes need an Alpha Vantage or Finnhub key, set through
`MARKET_DATA_PROVIDER` and `MARKET_DATA_API_KEY`. To reuse the skill outside
the repository, package it for pip and register it through the SDK's
`signalwire.skills` entry point. `add_skill("stock_quote")` then finds it with
no `add_skill_directory` call; the upstream README carries the
`pyproject.toml` for that. The recipe `write-a-reusable-agent-skill` is the
verified 3.0.1 version of the mechanism.

## What to change first

Open `config.py`. `MARKET_DATA_PROVIDER` and `MARKET_DATA_API_KEY` (set in
`.env`) pick the provider; to add one, write a
`yourprovider_quote(symbol, params)` function in `skills/stock_quote/skill.py`
that returns `{symbol, name, price, change, change_pct}` and add it to
`PROVIDERS`. `DESK_TICKERS`, `DESK_TOOL_NAME` and `DESK_COMPANY` set the second
agent's scope, and `skill_params()` holds the params both agents start from.
