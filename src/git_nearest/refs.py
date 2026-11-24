"""Select branch refs and rank their tips by distance from a commit."""
from collections import namedtuple

from .gitutil import git

HEADS = "refs/heads/"
REMOTES = "refs/remotes/"

Row = namedtuple("Row", "ahead behind ref full_ref oid")
REF_FIELDS = "%(refname)%09%(objectname)%09%(objecttype)%09%(symref)"


def _fields(out):
    return (line.split("\t") for line in out.split("\n") if line)


def _eligible(full_ref, object_type, symref, skip):
    return object_type == "commit" and not symref and full_ref != skip


def _candidates(namespaces, skip, pattern):
    out = git("for-each-ref", "--format=" + REF_FIELDS, *namespaces, strip=False)
    return {
        full_ref: oid for full_ref, oid, object_type, symref in _fields(out)
        if _eligible(full_ref, object_type, symref, skip)
        and (pattern is None or pattern.search(full_ref))
    }


def branch_tips():
    """Snapshot local and remote-tracking branches without symbolic aliases."""
    return _candidates((HEADS, REMOTES), None, None)


def _row(full_ref, oid, counts):
    # Git reports commits exclusive to the candidate first, then to the starting commit.
    behind, ahead = map(int, counts.split())
    return Row(ahead, behind, full_ref.split("/", 2)[2], full_ref, oid)


def _counts_native(base, namespaces, skip, candidates):
    """Batch counts with Git 2.41 or newer, using stdin for explicit ref names."""
    args = ("for-each-ref", "--format=" + REF_FIELDS + "%09%(ahead-behind:" + base + ")")
    if candidates is None:
        out = git(*args, *namespaces, check=False, strip=False)
    else:
        out = git(*args, "--stdin", input="\n".join(candidates) + "\n", check=False, strip=False)
    if not out:
        return None
    return [
        _row(full_ref, oid, counts)
        for full_ref, oid, object_type, symref, counts in _fields(out)
        if _eligible(full_ref, object_type, symref, skip)
        and (candidates is None or full_ref in candidates) and counts
    ]


def _counts_fallback(base, candidates):
    """Run one rev-list per distinct candidate tip on older Git."""
    counts = {}
    rows = []
    for full_ref, oid in candidates.items():
        if oid not in counts:
            counts[oid] = git("rev-list", "--left-right", "--count", oid + "..." + base)
        rows.append(_row(full_ref, oid, counts[oid]))
    return rows


def rank(limit, base="HEAD", skip=None, native=True, pattern=None):
    """Return aliases for the closest tips, sorted by ahead then behind counts.

    Match a supplied regex against full local and remote ref names. Without a regex,
    consider only remote refs. The limit counts distinct tips and skip is a full refname.
    """
    namespaces = (HEADS, REMOTES) if pattern is not None else (REMOTES,)
    candidates = None
    if pattern is not None:
        candidates = _candidates(namespaces, skip, pattern)
        if not candidates:
            return []

    rows = _counts_native(base, namespaces, skip, candidates) if native else None
    if rows is None:
        if candidates is None:
            candidates = _candidates(namespaces, skip, pattern)
        rows = _counts_fallback(base, candidates)

    groups = {}
    for row in sorted(rows, key=lambda r: (r.ahead, r.behind, r.ref, r.full_ref)):
        groups.setdefault(row.oid, []).append(row)
    return [row for group in list(groups.values())[:limit] for row in group]
