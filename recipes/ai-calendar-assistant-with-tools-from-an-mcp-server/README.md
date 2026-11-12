# AI calendar assistant over MCP: tools from an MCP server on a live call, scoped by the token

> A calendar assistant demo built to show MCP tools reaching a live call through one add_mcp_server call. The bearer token sets the tool list, the server holds the rules, and a caller ID signature keeps meetings to their owner.

**Scenario:** A phone line books and moves appointments with calendar tools that live behind an MCP server the platform connects to at call start

## What this demonstrates

MCP tools on a live call, with code deciding which ones the phone agent gets.
`add_mcp_server(MCP_URL, headers={"Authorization": "Bearer <MCP_TOKEN>"})`
renders `ai.SWAIG.mcp_servers` in the SWML. SignalWire's platform, not your
agent process, connects to that URL when each call starts. It runs
`initialize` and `tools/list`, adds the tools to the call as SWAIG functions,
and sends their `tools/call` requests straight to the MCP server. That is why
the tools do not appear in `SWAIG.functions` in a local dump, and why
`MCP_URL` must be a public HTTPS URL on a live call. The token is the scope:
the reference server maps each bearer token to a tool list.
`cancel_meeting` needs `MCP_ADMIN_TOKEN`, so it is never even listed to the
phone agent.

Callers reach a dental scheduling line. The agent asks for their name, then
books a new appointment in a free slot or moves an existing one. The calendar
is not in the agent at all; it lives behind an MCP server. The recipe ships a
small reference calendar server, `mcp_calendar.py`, in memory over streamable
HTTP. It is mounted in the same app at `/mcp-calendar`, so one public URL
covers both the SWML and the MCP server. Any other calendar MCP server can
replace it through `MCP_URL` and `MCP_TOKEN`.

## How it works

The server holds the rules and the data: weekday and office-hour checks,
30-minute marks, no double booking, nothing in the past. `find_free_slots`
returns times only, never whose meeting is in the way. The server, not the
model, knows who is calling. The agent's dynamic config renders this call's
MCP entry with the caller's number and an HMAC of it (`X-Caller`,
`X-Caller-Sig`). `find_my_meetings` takes no arguments and lists only that
number's meetings, and `move_meeting` refuses any meeting id that is not the
caller's. Caller ID is the identity here, so it is only as strong as the
caller ID the call arrives with. The SDK cannot scope MCP tools per step,
because `set_functions()` refuses a name that is not a locally registered
tool. The hard limits are the token and the server. The one local tool is
`get_today`, with a loop guard: after `GET_TODAY_MAX_CALLS` it says the
calendar is unavailable and switches itself off with `toggle_functions`.

Where each mechanism lives in the repository:

- `add_mcp_server(url, headers)`: `app.py`, `CalendarAgent.per_call_mcp`
- the reference MCP server mounted in the agent: `app.py`, `self.mount(mcp_calendar.create_router(...), prefix=config.MCP_CALENDAR_PATH)`
- token scopes: `config.MCP_SCOPES`, enforced in `mcp_calendar.py`, `create_router`
- per-call MCP headers through `set_dynamic_config_callback`: `per_call_mcp`, checked by `mcp_calendar.verified_caller`
- the server-side slot rules: `mcp_calendar.py`, `Calendar._check_slot`
- the local tool with a loop guard: `app.py`, `get_today`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a reference MCP server. It
pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The reference server keeps everything in memory, so a restart resets the
calendar; for anything real, use your own calendar MCP server. The MCP token
travels inside the SWML document, which is one more reason to give it the
narrowest scope that works. An external MCP server ignores the caller headers
unless it checks them the same way. The recipe
`call-an-mcp-server-from-a-live-call` is on hold here because the 3.0.1 schema
rejects `mcp_servers`; this build runs on a newer SDK where it validates.

## What to change first

Open `config.py`. `MCP_URL` and `MCP_TOKEN` (set in `.env`) point at your real
calendar MCP server. Ask its owner for a token scoped to what a phone caller
should be able to do. `GET_TODAY_MAX_CALLS` is how many `get_today` calls one
call gets before the agent gives up. `MCP_SCOPES`, `OFFICE_HOURS`,
`SLOT_MINUTES` and `SEED_MEETINGS` are the reference server's scopes and
rules, if you keep it. `BUSINESS_NAME`, `VOICE` and the "Rules" prompt section
in `app.py` round it out.
