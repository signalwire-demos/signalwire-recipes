# SignalWire Recipes

Small, self-contained examples on the SignalWire platform. Each folder is one
idea with one claim, and a verifier that proves the claim offline, with no
account and no network.

122 recipes, each with a verifier that proves its claim.

## Running one

```bash
git clone https://github.com/signalwire-demos/signalwire-recipes.git
cd signalwire-recipes
pip install -r requirements.txt -r recipes/<slug>/python/requirements.txt
python verify.py <slug>          # proves the claim, no credentials needed
```

The root requirements are the verifier's tooling; each recipe pins its own SDK
and framework in its `python/requirements.txt`, so both are installed.

Then read `recipes/<slug>/README.md` and run the surface you want. Every recipe
ships a `.env.example` and commits no secrets.

`recipes/README.md` is the index of every folder here, by product line.

## Licence

MIT. See `LICENSE`.
