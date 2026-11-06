"""Rebuild the artifact of an extracted obs-html source archive with the obs that built it.

Reader: whoever rebuilds an artifact from its source archive, or changes how the archive rebuilds;
obs-html's input-model.md, "Optional reproduction archive", owns the behaviour.

obs-html copies this file into every source archive as ``reproduce.py``. From the extracted folder,
``python reproduce.py`` clones obs from the repository ``build-config.json`` names (``--repository``
names another, such as a local clone), checks out the recorded commit, installs it with that
commit's uv.lock and runs the recorded obs-document command on ``vault/``. It needs git and uv and
imports nothing beyond Python's standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHECKOUT = "obs"
"""The folder, beside this file, that holds obs at the recorded commit."""


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    remedy: str
    environment: dict[str, str] = field(default_factory=dict)


def steps(config: dict, here: Path, repository: str, execute_commands: bool) -> list[Step]:
    """The steps that rebuild the artifact in ``here``; a checkout left by an earlier run is reused."""
    commit, command = config["obs"]["commit"], config["command"]
    if "--execute-commands" in command and not execute_commands:
        raise SystemExit("reproduce.py: build-config.json: command: the recorded build ran the vault's command "
                         "fences (--execute-commands). Remedy: review vault/, then run python reproduce.py "
                         "--execute-commands.")
    checkout = here / CHECKOUT
    clone = [] if checkout.exists() else [Step(
        "clone", ["git", "clone", "--quiet", "--no-checkout", repository, str(checkout)],
        f"check that {repository} is reachable, or clone obs yourself and pass the clone: python reproduce.py "
        f"--repository <folder>; or delete {checkout} if an earlier run left it broken")]
    return [*clone,
            Step("checkout", ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", commit],
                 f"pass a clone that holds commit {commit} with --repository, after deleting {checkout}"),
            Step("install", ["uv", "sync", "--frozen", "--project", str(checkout)],
                 "install uv (https://docs.astral.sh/uv/) and check that the package index is reachable"),
            Step("rebuild", ["uv", "run", "--frozen", "--project", str(checkout), *command,
                             "--adapter-config", str(checkout / "adapters.json")],
                 "the obs-document message above names the cause", {"UV_PROJECT": str(checkout)})]


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    config = json.loads((here / "build-config.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(prog="reproduce.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repository", default=config["obs"]["repository"],
                        help="The repository URL or local clone to install obs from (default: the recorded one).")
    parser.add_argument("--execute-commands", action="store_true",
                        help="Allow the recorded command to run the vault's command fences; review vault/ first.")
    options = parser.parse_args(argv)
    commit = config["obs"]["commit"]
    for step in steps(config, here, options.repository, options.execute_commands):
        try:
            # The adapter's own uv run, started by obs-document, finds obs through UV_PROJECT.
            result = subprocess.run(step.command, cwd=here, env={**os.environ, **step.environment},
                                    capture_output=step.name != "rebuild", text=True)
            detail = (result.stderr or "").strip() if result.returncode else None
        except FileNotFoundError:
            detail = f"{step.command[0]} is not installed"
        if detail is not None:
            raise SystemExit(f"reproduce.py: {step.name}: obs commit {commit} from {options.repository} failed"
                             f"{': ' + detail if detail else ''}. Remedy: {step.remedy}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
