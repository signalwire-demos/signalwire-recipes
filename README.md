# SignalWire Recipes

Small, self-contained examples on the SignalWire platform. Each folder is one
idea with one claim, and a verifier that proves the claim offline, with no
account and no network.

121 recipes, each with a verifier that proves its claim.

## Running one

```bash
git clone https://github.com/signalwire-demos/signalwire-recipes.git
cd signalwire-recipes
pip install -r requirements.txt
python verify.py <slug>          # proves the claim, no credentials needed
```

Then read `recipes/<slug>/README.md` and run the surface you want. Every recipe
ships a `.env.example` and commits no secrets.

`recipes/README.md` is the index of every folder here, by product line.

## Licence

MIT. See `LICENSE`.
