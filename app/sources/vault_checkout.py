"""Keep a local clone of the vault repo up to date, so reads never touch the slow
cloud-synced Obsidian folder. Read only: clone or hard-reset to origin, never push."""

import os
import shlex
import subprocess
from pathlib import Path


def resolved_vault_path(settings) -> str:
    """Where to read the vault from right now: the checkout (kept fresh by the
    periodic sync job) when configured, else the raw vault_path. No I/O here,
    callers that need it current should run a sync first or call ensure_checkout."""
    return (
        settings.obsidian_checkout_dir
        if settings.obsidian_repo_url
        else settings.obsidian_vault_path
    )


def write_eod_log(vault_path: str, day: str, content: str) -> None:
    """The one write this app makes into the vault: one file a day, a fixed folder, a fixed
    name. Always the real vault_path, never the read-only checkout, writes don't go through git."""
    if not vault_path:
        raise FileNotFoundError("OBSIDIAN_VAULT_PATH is not set")
    p = Path(vault_path) / "daily-agent-logs" / f"{day}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


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
