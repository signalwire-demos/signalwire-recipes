#!/usr/bin/env python3
"""Run every recipe's verify.py and refuse on the first lie.

A recipe's claim is proven by `recipes/<slug>/verify.py`: construct the thing,
render the artifact the platform would receive (SWML, a REST request, a webhook
reply), and assert the mechanism in that artifact. Compilation is not proof; a
recipe that merely imports does not count.

    python verify.py                # every recipe that has a verify.py
    python verify.py <slug> [...]   # just these

The SDK is resolved from SIGNALWIRE_SDK_PATH, else the vendored 3.0.1 next to
this repo. The path is absolute on purpose: a relative PYTHONPATH falls back to
whatever `signalwire` is in site-packages after any `cd`.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
RECIPES = ROOT / "recipes"
SDK = os.environ.get(
    "SIGNALWIRE_SDK_PATH",
    str((ROOT.parent / "AI Call Center" / "signalwire-call-center" / "ai-agents"
         / "signalwire-sdk" / "signalwire").resolve()),
)


def main(argv):
    wanted = set(argv[1:])
    targets = sorted(
        p for p in RECIPES.glob("*/verify.py")
        if not wanted or p.parent.name in wanted
    )
    if not targets:
        print("no verify.py found" + (f" for {sorted(wanted)}" if wanted else ""))
        return 1
    env = dict(os.environ, PYTHONPATH=SDK, PYTHONIOENCODING="utf-8")
    failed = []
    for t in targets:
        slug = t.parent.name
        r = subprocess.run([sys.executable, str(t)], cwd=t.parent, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        if r.returncode == 0:
            print(f"  ok    {slug}: {tail}")
        else:
            failed.append(slug)
            print(f"  FAIL  {slug}")
            for line in (r.stderr.strip().splitlines() or r.stdout.strip().splitlines())[-8:]:
                print(f"        {line}")
    n = len(targets)
    print(f"verify: {n - len(failed)} of {n} recipes prove their claim"
          + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
