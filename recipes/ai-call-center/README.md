# AI Call Center

> A complete contact centre: AI triage, priority queues, live human agents, supervisor monitoring, and transfers that keep their context.

## What this demonstrates

Every governance and handoff pattern in the recipes, running together in one
product rather than in isolation. The AI answers, gathers intake under scoped
tools, and hands to a human queue with the context intact; supervisors can listen,
whisper, or take over; callers who will not wait get a callback that remembers why
they called.

It exists because a directory of single-idea recipes leaves one question open: whether
the patterns compose. This is the answer to that question.

## How it works

Ten recipes, wired together. Each one is documented on its own page; this build
shows them in the same call flow, with the state that has to survive between them.

## Limitations

This is a full application, not a snippet. It needs Postgres, Redis, and a
provisioned SignalWire workspace, and it is a clone-and-own product rather than
something you copy a function out of.

## What to change first

The queue routing rules, then the agent prompts. Both are configuration rather
than code.
