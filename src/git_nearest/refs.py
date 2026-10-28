"""Rank remote refs by how close they are to HEAD."""
from collections import namedtuple

from .gitutil import git

REMOTES = "refs/remotes/"

Row = namedtuple("Row", "ahead behind ref")  # ref is the short name, e.g. origin/main


def _counts_native():
    """One git call for every ref; needs git >= 2.41 (%(ahead-behind:...))."""
    out = git("for-each-ref", "--format=%(ahead-behind:HEAD)%09%(refname)", REMOTES, check=False)
    if not out:
        return None
    return [line.split("\t") for line in out.splitlines()]


def _counts_fallback():
    """One rev-list per ref, for older git."""
    names = git("for-each-ref", "--format=%(refname)", REMOTES).splitlines()
    pairs = []
    for name in names:
        if not name.endswith("/HEAD"):
            pairs.append((git("rev-list", "--left-right", "--count", name + "...HEAD"), name))
    return pairs


def rank(limit, native=True):
    """Closest remote refs first: fewest commits HEAD is ahead by, then fewest it is behind by."""
    pairs = (_counts_native() if native else None) or _counts_fallback()
    rows = []
    for counts, name in pairs:
        if name.endswith("/HEAD"):  # origin/HEAD is just a pointer
            continue
        # "<only in ref = behind> <only in HEAD = ahead>"
        behind, ahead = counts.split()
        rows.append(Row(int(ahead), int(behind), name[len(REMOTES):]))
    rows.sort(key=lambda r: (r.ahead, r.behind, r.ref))
    return rows[:limit]
