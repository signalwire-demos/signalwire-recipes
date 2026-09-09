# Embed a state-aware voice agent in your web page

> A voice and video agent in a floating widget on a documentation site. It answers from the docs through a hosted search tool, navigates the reader to the right page and scrolls them to the right section, and knows which page they are on.

## What this demonstrates

An agent that does not only talk about a web page but drives it. The reader
presses a button on the docs site, a Fabric call opens in the widget, and the
agent's tools reach back into the page: `search_docs` answers from a hosted
index of the docs, `navigate` and `scroll_to` fire `user_event` actions the
widget turns into route changes and scroll positions. The widget posts the
reader's current page back to the agent, so the prompt always knows where they
are. The agent has a face, from three video files, and speaks a filler while
each tool runs.

It exists to show that the browser recipes compose: a token minted for one
address, events pushed to the page, state kept on the server, and a prompt
reconfigured per call are one product when wired together. A deployment is
live at https://harbor-docs-5k2.pages.dev/ and the widget is the button in
the corner.

## How it works

Ten recipes, in two repositories. The site is an Astro Starlight project with a
React widget; the agent is an `AgentBase` with four tools. The widget asks the
agent for a guest token, dials the agent's Fabric address with the Browser SDK,
and listens for `user_event`. The agent seeds each call's `global_data` from
the page the widget reports, keeps the rest of the page state in memory, and
pushes silent `global_data` updates into the live call with `calling.ai_message`
when the reader moves. Retrieval runs against DataSphere, so the agent carries
no index and runs as a Lambda behind a function URL.

## Limitations

This is two deployments, not a snippet: a static site with a Cloudflare Pages
function for its runtime config, and an agent on Lambda with a DataSphere
corpus uploaded ahead of time. The site is in the linked repository; the agent
lives in the testing-protocol workspace and does not yet have a repository of
its own, so the link above is half the code.

The agent is tuned against a suite of scripted and adaptive test calls. Its
prompt carries several corrections that only that testing found, and it would
not survive a corpus change without re-running the suite.

## What to change first

The corpus and the catalog. `scripts/seed-docs.mjs` in the site and
`upload_index.py` in the agent are what make it about one product's docs
rather than another's; the tools and the widget do not change.
