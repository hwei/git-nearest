"""The default output: one line per ref with ahead/behind and the merge-base."""
from . import color
from .gitutil import git


def render(rows, paint, base, head_line=None):
    ups = ["↑%d" % r.ahead for r in rows]
    downs = ["↓%d" % r.behind for r in rows]
    wa, wb, wn = max(map(len, ups)), max(map(len, downs)), max(len(r.ref) for r in rows)
    lines = [head_line] if head_line else []
    for r, up, down in zip(rows, ups, downs):
        mb = git("merge-base", "refs/remotes/" + r.ref, base, check=False)[:8]
        lines.append("%s %s  %s  %s" % (
            paint(color.GREEN, up.ljust(wa)),
            paint(color.RED, down.ljust(wb)),
            r.ref.ljust(wn),
            paint(color.DIM, mb),
        ))
    return lines
