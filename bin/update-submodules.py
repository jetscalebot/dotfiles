#!/usr/bin/env python3
"""Advance top-level submodules to their configured remote branches and stage them."""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
from pathlib import Path


def git(
    *args: str,
    cwd: Path,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        env=env,
    )


def main() -> int:
    root = Path(
        git("rev-parse", "--show-toplevel", cwd=Path.cwd(), capture_output=True).stdout.strip()
    )
    modules_file = root / ".gitmodules"
    if not modules_file.exists():
        print("No .gitmodules file; nothing to update.")
        return 0

    config = configparser.ConfigParser()
    config.read(modules_file)
    paths = [
        config[section]["path"]
        for section in config.sections()
        if section.startswith('submodule "') and "path" in config[section]
    ]
    if not paths:
        print("No submodules configured; nothing to update.")
        return 0

    # Commit hooks export parent-repository paths, including a possibly relative
    # GIT_INDEX_FILE. These must not leak into commands run in a submodule.
    local_env_vars = git(
        "rev-parse", "--local-env-vars", cwd=root, capture_output=True
    ).stdout.splitlines()
    submodule_env = {key: value for key, value in os.environ.items() if key not in local_env_vars}

    for relative_path in paths:
        submodule = root / relative_path
        if not submodule.exists():
            continue
        status = git(
            "status",
            "--porcelain",
            "--ignore-submodules=none",
            cwd=submodule,
            capture_output=True,
            env=submodule_env,
        ).stdout
        if status:
            print(
                f"Refusing to update dirty submodule {relative_path}:\n{status}",
                file=sys.stderr,
            )
            return 1

    git("submodule", "sync", "--", *paths, cwd=root)
    git("submodule", "update", "--init", "--remote", "--checkout", "--", *paths, cwd=root)
    git("add", "--", *paths, cwd=root)
    print(f"Updated and staged {len(paths)} top-level submodule(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Git command failed (exit {error.returncode}): {error.cmd}", file=sys.stderr)
        raise SystemExit(error.returncode) from error
