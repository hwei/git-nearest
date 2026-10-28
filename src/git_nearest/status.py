"""Working tree state of HEAD: is it clean, and if not, how dirty."""
from collections import namedtuple

from . import color
from .gitutil import git

Counts = namedtuple("Counts", "staged modified untracked conflicted")


def read():
    counts = dict(staged=0, modified=0, untracked=0, conflicted=0)
    for line in git("status", "--porcelain=v1", strip=False).splitlines():
        x, y = line[0], line[1]
        if x == "!":
            continue
        if x == "?":
            counts["untracked"] += 1
        elif "U" in (x, y) or (x, y) in (("A", "A"), ("D", "D")):
            counts["conflicted"] += 1
        else:
            counts["staged"] += x != " "
            counts["modified"] += y != " "
    return Counts(**counts)


def describe(counts, paint):
    """'[clean]' or e.g. '[2 staged, 3 modified, 1 untracked]'."""
    parts = ["%d %s" % (n, name) for name, n in counts._asdict().items() if n]
    if not parts:
        return paint(color.GREEN, "[clean]")
    return paint(color.RED if counts.conflicted else color.YELLOW, "[%s]" % ", ".join(parts))
