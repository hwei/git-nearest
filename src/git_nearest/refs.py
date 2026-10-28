"""Rank remote refs by how close they are to HEAD."""
from collections import namedtuple

from .gitutil import git

REMOTES = "refs/remotes/"

Row = namedtuple("Row", "ahead behind ref")  # ref is the short name, e.g. origin/main


def _counts_native(base):
    """One git call for every ref; needs git >= 2.41 (%(ahead-behind:...))."""
    out = git("for-each-ref", "--format=%(ahead-behind:" + base + ")%09%(refname)", REMOTES, check=False)
    if not out:
        return None
    return [line.split("\t") for line in out.splitlines()]


def _counts_fallback(base):
    """One rev-list per ref, for older git."""
    names = git("for-each-ref", "--format=%(refname)", REMOTES).splitlines()
    pairs = []
    for name in names:
        if not name.endswith("/HEAD"):
            pairs.append((git("rev-list", "--left-right", "--count", name + "..." + base), name))
    return pairs


def rank(limit, base="HEAD", skip=None, native=True):
    """Closest remote refs first: fewest commits base is ahead by, then fewest it is behind by.

    skip is a full refname to leave out (the ref we are measuring from).
    """
    pairs = (_counts_native(base) if native else None) or _counts_fallback(base)
    rows = []
    for counts, name in pairs:
        if name == skip or name.endswith("/HEAD"):  # origin/HEAD is just a pointer
            continue
        # "<only in ref = behind> <only in base = ahead>"
        behind, ahead = counts.split()
        rows.append(Row(int(ahead), int(behind), name[len(REMOTES):]))
    rows.sort(key=lambda r: (r.ahead, r.behind, r.ref))
    return rows[:limit]
