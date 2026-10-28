"""`jj log`-style graph (newest on top) of HEAD and the given remote refs.

Only the commits that matter are drawn: HEAD, the ref tips and the merge-bases between them.
Everything in between is folded into a "~  (n)" row on the vertical line.
"""
from . import color
from .gitutil import git

LINE_GLYPHS = set("│├┴┼╯╮┤─~")  # │ ├ ┴ ┼ ╯ ╮ ┤ ─ ~
LEGEND = "~ (n) = n commits folded between"


def render(refs, paint, head, label, head_note=None):
    """head: the commit everything is measured from; label: how to name it (e.g. "HEAD -> main")."""
    names = {}  # commit -> remote refs pointing at it
    shas = git("rev-parse", *["refs/remotes/" + r for r in refs]).split()
    for ref, sha in zip(refs, shas):
        names.setdefault(sha, []).append(ref)
    tips = sorted(set(names) | {head})
    tip_bit = {c: 1 << i for i, c in enumerate(tips)}

    # Load the history above the common base: children come before parents in `order`.
    base = git("merge-base", "--octopus", *tips, check=False)
    rev = ["rev-list", "--topo-order", "--parents", *tips] + (["^" + base] if base else [])
    parents = {}
    order = []
    for line in git(*rev).splitlines():
        commit, *ps = line.split()
        parents[commit] = ps
        order.append(commit)
    if base:
        parents[base] = []
        order.append(base)
    for commit in order:
        parents[commit] = [p for p in parents[commit] if p in parents]

    # mask[c] = which tips can reach c. Commits sharing a mask form one region; the newest commit
    # of each region (no child with the same mask) is where branches split: a merge-base.
    mask = {c: tip_bit.get(c, 0) for c in order}
    for c in order:
        for p in parents[c]:
            mask[p] |= mask[c]
    has_twin_child = {p for c in order for p in parents[c] if mask[p] == mask[c]}
    nodes = [c for c in order if c in tip_bit or c not in has_twin_child]
    node_bit = {c: 1 << i for i, c in enumerate(nodes)}

    # allanc[c] = bitmask of every node below c; the nearest are those no other ancestor node covers.
    allanc = {}
    for c in reversed(order):
        a = 0
        for p in parents[c]:
            a |= allanc[p] | node_bit.get(p, 0)
        allanc[c] = a

    def on_head_line(c):
        return c == head or bool(allanc[head] & node_bit[c]) or bool(allanc[c] & node_bit[head])

    # Newest first among the nodes that are ready to draw; children still always come before parents.
    when = {}
    for line in git("show", "-s", "--format=%H %ct", *nodes).splitlines():
        sha, ts = line.split()
        when[sha] = int(ts)

    def sort_key(c):
        return (-when[c], not on_head_line(c), sorted(names.get(c, [c]))[0])

    above = {}   # node -> nearest ancestor nodes, head line first
    folded = {}  # node -> commits between it and those ancestors
    for c in nodes:
        a = allanc[c]
        covered = 0
        for n in nodes:
            if a & node_bit[n]:
                covered |= allanc[n]
        above[c] = sorted((n for n in nodes if a & ~covered & node_bit[n]), key=sort_key)
        if above[c]:
            own = int(git("rev-list", "--count", c, *["^" + p for p in above[c]]) or 1)
            folded[c] = own - 1

    def node_text(c):
        parts = []
        if c == head:
            parts.append(paint(color.GREEN_BOLD, label))
        parts += [paint(color.CYAN, n) for n in sorted(names.get(c, []))]
        if not parts:
            parts.append(paint(color.DIM, "merge-base"))
        text = "%s  %s" % (paint(color.DIM, c[:8]), ", ".join(parts))
        return text + "  " + head_note if c == head and head_note else text

    def marker(c):
        if c == head:
            return paint(color.GREEN_BOLD, "@")
        return paint(color.CYAN if c in names else color.DIM, "○")  # ○

    out = []
    lanes = []  # lanes[i] = the node lane i is heading to (None = free)

    def emit(cells, fill=(), width=0, text=""):
        """One row. cells: lane -> glyph (default: a vertical line on an active lane);
        fill: lanes joined to the next one by a horizontal line."""
        n = max([i for i, c in enumerate(lanes) if c is not None] + [width - 1, *cells]) + 1
        row = ""
        for i in range(n):
            glyph = cells.get(i) or ("│" if i < len(lanes) and lanes[i] else " ")
            row += paint(color.DIM, glyph) if glyph in LINE_GLYPHS else glyph
            row += paint(color.DIM, "─") if i in fill else " "
        out.append(("%s %s" % (row, text)).rstrip())

    def free_lane(after=-1):
        for i in range(after + 1, len(lanes)):
            if lanes[i] is None:
                return i
        lanes.append(None)
        return len(lanes) - 1

    def draw(c):
        waiting = [i for i, n in enumerate(lanes) if n == c]
        if not waiting:
            k = free_lane()
            lanes[k] = c
            waiting = [k]
        k, extra = waiting[0], waiting[1:]
        if extra:  # lanes of other children converge onto this node
            cells = {k: "├", **{j: "┴" for j in extra}, extra[-1]: "╯"}
            for i in range(k + 1, extra[-1]):
                cells.setdefault(i, "┼" if lanes[i] else "─")
            emit(cells, fill=range(k, extra[-1]))
            for j in extra:
                lanes[j] = None
        emit({k: marker(c)}, width=k + 1, text=node_text(c))

        ps = above[c]
        lanes[k] = ps[0] if ps else None
        for p in ps[1:]:  # merge: a second parent gets its own lane (or joins the one already heading there)
            joined = p in lanes
            j = lanes.index(p) if joined else free_lane(k)
            lanes[j] = p
            lo, hi = min(k, j), max(k, j)
            cells = {lo: "├", hi: "┤" if joined else "╮"}
            for i in range(lo + 1, hi):
                cells[i] = "┼" if lanes[i] else "─"
            emit(cells, fill=range(lo, hi))
        if folded.get(c):
            emit({k: "~"}, text=paint(color.DIM, "(%d)" % folded[c]))

    pending = {c: 0 for c in nodes}
    for c in nodes:
        for a in above[c]:
            pending[a] += 1
    ready = [c for c in nodes if pending[c] == 0]
    while ready:
        ready.sort(key=sort_key)
        c = ready.pop(0)
        draw(c)
        for a in above[c]:
            pending[a] -= 1
            if pending[a] == 0:
                ready.append(a)
    out.append(paint(color.DIM, LEGEND))
    return out
