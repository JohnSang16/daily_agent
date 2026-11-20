"""Keep a local clone of the vault repo up to date, so reads never touch the slow
cloud-synced Obsidian folder. Read only: clone or hard-reset to origin, never push."""

import os
import shlex
import subprocess
from pathlib import Path


def ensure_checkout(repo_url: str, deploy_key_path: str, checkout_dir: str) -> str:
    # absolute: git fetch runs inside the checkout, where a relative key path points nowhere
    key = shlex.quote(str(Path(deploy_key_path).expanduser().resolve()))
    ssh = f"ssh -i {key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
    env = {**os.environ, "GIT_SSH_COMMAND": ssh}  # keep PATH and HOME for git and ssh
    root = Path(checkout_dir)
    if (root / ".git").is_dir():
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin"],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
        )
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "reset", "--hard", f"origin/{branch}"],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
        )
    else:
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(root)],
            env=env,
            check=True,
            capture_output=True,
        )
    return str(root)
