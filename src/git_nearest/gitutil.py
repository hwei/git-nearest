"""Thin wrapper around the git executable."""
import subprocess


class GitError(Exception):
    pass


def git(*args, check=True, strip=True):
    """Run git and return stdout (stripped unless strip is False).

    On failure raise GitError, or return "" when check is False.
    """
    try:
        p = subprocess.run(
            ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        raise GitError("git executable not found")
    if p.returncode != 0:
        if check:
            raise GitError(p.stderr.strip() or "git " + " ".join(args) + " failed")
        return ""
    return p.stdout.strip() if strip else p.stdout
