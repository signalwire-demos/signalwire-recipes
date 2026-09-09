# SignalWire Recipes

Small, self-contained examples on the SignalWire platform. Each folder is one
idea with one claim, and a verifier that proves the claim offline, with no
account and no network.

121 of 146 folders are written; the rest are planned.

## Running one

```bash
git clone https://github.com/signalwire-demos/signalwire-recipes.git
cd signalwire-recipes
pip install -r requirements.txt
python verify.py <slug>          # proves the claim, no credentials needed
```

Then read `recipes/<slug>/README.md` and run the surface you want. Every recipe
ships a `.env.example` and commits no secrets.

`recipes/README.md` is the index of every folder here.

## About this repository

This repository is generated and read-only. It is published from a private
repository inside SignalWire, which holds the same recipes together with the
generator that renders them into a website. Changes are made there and appear
here when the next build runs, so a change committed here would be overwritten.

Issues and pull requests are not monitored. If you work at SignalWire, use the
source repository. If you do not, and something here is wrong, please reach out
through the support channels on signalwire.com.

## Licence

MIT. See `LICENSE`.
