"""Prove the claim without a network.

Claim: the SDK's `swaig-test` CLI loads an agent file and, with no number,
tunnel or account, dumps the SWML the platform would fetch, lists the tools,
and runs a tool with the arguments you give it.

Proof: run the CLI as a subprocess against python/app.py four times, with a
child environment that carries only the SDK path and the basic-auth pair, so
no account credential can reach it. The `--dump-swml --raw` output parses as
JSON, validates against the bundled schema, and carries the one tool.
`--list-tools` prints the tool's block with its description and its required
parameter. `--exec check_hours --day saturday` prints `RESULT:` and then the
handler's exact response on the `FunctionResult:` line, and an invalid day
prints its refusal the same way. Expected values live here, not in app.py.
"""
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))

import verifylib as V  # noqa: E402

# fixed, verifier-only credentials: never a reader's real pair, so nothing this
# file prints can carry one
os.environ["SWML_BASIC_AUTH_USER"] = "signalwire"
os.environ["SWML_BASIC_AUTH_PASSWORD"] = "verify-only-password"

APP = HERE / "python" / "app.py"
SATURDAY = "On Saturday the shop is open 9 to 5."
INVALID = "INVALID: ask for a day of the week."


def swaig_test(*args):
    """Run the CLI the way a developer does, as its own process, with an
    environment that holds no account credential."""
    import signalwire
    keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG")
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["SWML_BASIC_AUTH_USER"] = os.environ["SWML_BASIC_AUTH_USER"]
    env["SWML_BASIC_AUTH_PASSWORD"] = os.environ["SWML_BASIC_AUTH_PASSWORD"]
    # the directory that holds the `signalwire` package, so the child sees
    # the same SDK this verifier loaded
    env["PYTHONPATH"] = str(pathlib.Path(signalwire.__file__).parent.parent)
    cmd = [sys.executable, "-m", "signalwire.cli.swaig_test_wrapper", str(APP), *args]
    # a clean clone has no .env anywhere load_dotenv() searches: python/, the
    # recipe folder, and every parent up to the filesystem root. app.py would
    # read one if you created it, and this verifier refuses to run against any.
    for folder in [HERE / "python", HERE, *HERE.parents]:
        assert not (folder / ".env").exists(), f"remove {folder / '.env'} before verifying"
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120,
                       cwd=str(HERE))
    assert r.returncode == 0, (args, r.returncode, r.stderr[-800:])
    return r.stdout


def result_line(out):
    """The FunctionResult line that follows RESULT:, whitespace normalised."""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    i = lines.index("RESULT:")
    assert lines[i + 1].startswith("FunctionResult: "), lines[i:i + 2]
    return lines[i + 1][len("FunctionResult: "):]


def main():
    V.sdk_banner()

    # the document the platform would fetch, straight from the CLI
    out = swaig_test("--dump-swml", "--raw")
    doc = json.loads(out[out.index("{"):])
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    names = [f["function"] for f in ai["SWAIG"]["functions"]]
    assert names == ["check_hours"], names  # never echo SWAIG: its URLs carry credentials

    # the tool inventory: the tool's block, then its parameter, in that order
    out = swaig_test("--list-tools")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    head = "check_hours - Look up the shop's opening hours for a day of the week. (LOCAL webhook)"
    i = lines.index(head)
    assert lines[i + 1] == "Parameters:", lines[i:i + 3]
    assert lines[i + 2] == "day (string) (required): A day of the week, in English.", lines[i + 2]
    assert sum(ln.endswith("(LOCAL webhook)") for ln in lines) == 1, "one tool listed"

    # the handler, run with arguments and fake call data
    assert result_line(swaig_test("--exec", "check_hours", "--day", "saturday")) == SATURDAY
    assert result_line(swaig_test("--exec", "check_hours", "--day", "someday")) == INVALID

    print(f"ok: swaig-test dumped valid SWML with ['check_hours'], listed the tool "
          f"and its required 'day', and ran it: {SATURDAY!r} and the INVALID refusal")


if __name__ == "__main__":
    main()
