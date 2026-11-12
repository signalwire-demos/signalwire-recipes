# Give Claude a phone number: an AI phone line whose tools are also an MCP server

> A phone line demo built to show an AI agent's tools served as an MCP endpoint with its own credential. An allowlist keeps call-control tools off MCP, and the handlers carry the booking rules on both channels.

**Scenario:** Callers reach a support line; Claude Desktop reaches the same lookup and booking handlers over MCP, with transfers kept voice-only

## What this demonstrates

The agent as an MCP server, with code deciding what each channel can reach.
`enable_mcp_server()` exposes the agent's tools at `/mcp` behind its own
credential, a bearer token in `MCP_TOKEN`. The SWML basic auth in the number's
webhook URL does not open `/mcp`, and the token does not open the SWML routes.
`config.MCP_TOOLS` is an allowlist: `transfer_to_human` moves a live call, so
it stays voice-only, and an MCP client cannot list it or call it. An MCP
client has no steps, so the handlers carry their own rules. `book_callback`
refuses unknown accounts, past times, weekends and after-hours slots on both
channels.

Callers reach a fibre provider's support line. The agent asks for the phone
number on the account and looks it up in a mock CRM. Then it offers to book
a callback or transfer the call to a person. The same agent serves `POST /mcp`.
Point Claude Desktop, Claude Code or any MCP client at it. Ask for the
account on a number and a callback on Monday at 10:30. Claude calls
`lookup_customer` and `book_callback`: the same handlers, the same validation,
and the same bookings file the phone line writes to.

## How it works

The SDK's `/mcp` route checks auth through `_check_basic_auth()`, so the app
overrides that one method for the `/mcp` path only. The allowlist is one small
override of `_mcp_tools()`, the method the route uses both to list and to call
tools. Both are private hooks in 3.7.5, and the upstream tests fail if either
stops working after an upgrade. On a call, `book_callback` books for the
account `lookup_customer` put in `global_data`, whatever id the model passes.
Over MCP there is no call state, so it also needs the phone number on that
account, and a guessed account id alone books nothing. `lookup_customer`
returns only `account_id`, `name` and `plan`; the CRM's internal block never
reaches the phone model or Claude. Over MCP only the handler's response text
comes back. Actions such as `swml_change_step` are call-control instructions
and are dropped, which is why nothing call-moving belongs on the MCP list.

Where each mechanism lives in the repository:

- `enable_mcp_server()`: `app.py`, `PhoneAgent.__init__`
- the separate `/mcp` credential: `PhoneAgent._check_basic_auth`, token in `config.MCP_TOKEN`
- the MCP allowlist: `PhoneAgent._mcp_tools`, list in `config.MCP_TOOLS`
- `define_contexts`, `set_functions` and `set_valid_steps([])`: steps `identify` and `help`
- `update_global_data` then `swml_change_step`: `lookup_customer`
- `connect`, voice-only: `transfer_to_human`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock CRM under `data/`.
It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are
verified against. Its claims are proven by its own tests, not by a verifier in
this repository. The repository carries no licence file at the time of
writing, which is its owner's to add.

Anyone holding the MCP token can run `lookup_customer` for any phone number
they try, and there is no rate limit. Give it only to people who may look
customers up, and rotate it if it leaks. Bookings are appended to a local
file. The recipe `expose-an-agent-as-an-mcp-server` is on hold here because
`enable_mcp_server()` is broken in 3.0.1, where `tools/list` returns an empty
list. This build runs on 3.7.5, where it works.

## What to change first

Open `config.py`. `MCP_TOOLS` decides which tools MCP clients can reach; every
tool not listed is voice-only, and call-control tools stay off it.
`CUSTOMERS_FILE`, `CALLBACK_HOURS` and `CALLBACK_DAYS` point at your CRM and
booking rules. `BUSINESS_NAME`, `VOICE` and `HUMAN_NUMBER` (in `.env`) set the
voice side.
