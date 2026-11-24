"""Draw the selected branch tips and their history around an observation point."""
from collections import namedtuple

from . import color
from .gitutil import git

LINE_GLYPHS = set("│├┴┼╯╮┤─~")
LEGEND = "~ (n) = n commits folded between"
Row = namedtuple("Row", "text oid kind detail_prefix", defaults=(None, "text", ""))
_Continuation = namedtuple("_Continuation", "anchor outside")


def _history(tips):
    """Load commits and edges down to the common base, in children-first order."""
    if len(tips) == 1:
        tip = tips[0]
        return {tip: []}, {tip: 0}

    base = git("merge-base", "--octopus", *tips, check=False)
    rev = ["rev-list", "--topo-order", "--parents", "--timestamp", *tips]
    if base:
        rev.append("^" + base)
    parents = {}
    when = {}
    for line in git(*rev).splitlines():
        timestamp, commit, *parent_ids = line.split()
        parents[commit] = parent_ids
        when[commit] = int(timestamp)
    if base:
        parents[base] = []
        when[base] = int(git("show", "-s", "--format=%ct", base))
    for commit, parent_ids in parents.items():
        parents[commit] = [parent for parent in parent_ids if parent in parents]
    return parents, when


def _merge_bases(tips, parents):
    tip_bit = {commit: 1 << index for index, commit in enumerate(tips)}
    mask = {commit: tip_bit.get(commit, 0) for commit in parents}
    for commit in parents:
        for parent in parents[commit]:
            mask[parent] |= mask[commit]
    # A merge-base is the first commit of a region reachable from the same tips.
    has_twin_child = {
        parent for commit in parents for parent in parents[commit] if mask[parent] == mask[commit]
    }
    return set(parents) - has_twin_child


def _visible_parents(parents, visible, unfolded=()):
    """Find each commit's nearest visible ancestors, projecting through hidden commits."""
    closest = {}
    for commit in reversed(parents):
        candidates = set()
        for parent in parents[commit]:
            if parent in visible:
                candidates.add(parent)
            else:
                candidates.update(closest[parent])
        closest[commit] = candidates

    above = {commit: closest[commit] for commit in parents if commit in visible}
    # Keep direct merge edges in an unfolded region. Else a projected edge is
    # redundant when its target is reachable through one of the other targets.
    joins = {
        commit: candidates for commit, candidates in above.items()
        if len(candidates) > 1 and (commit not in unfolded or candidates != set(parents[commit]))
    }
    if joins:
        targets = set().union(*joins.values())
        target_bit = {target: 1 << index for index, target in enumerate(targets)}
        ancestors = {}
        for commit in reversed(parents):
            inherited = 0
            for parent in parents[commit]:
                inherited |= ancestors[parent] | target_bit.get(parent, 0)
            ancestors[commit] = inherited
        for commit, candidates in joins.items():
            covered = 0
            for candidate in candidates:
                covered |= ancestors[candidate]
            above[commit] = {candidate for candidate in candidates if not covered & target_bit[candidate]}
    return above


def _center_line(parents, center):
    older = {center}
    for commit, parent_ids in parents.items():
        if commit in older:
            older.update(parent_ids)
    newer = {center}
    for commit in reversed(parents):
        if any(parent in newer for parent in parents[commit]):
            newer.add(commit)
    return older | newer


def _region_args(anchor, boundary):
    return [anchor, *("^" + oid for oid in sorted(boundary))]


def _labels(commit, paint, names, center, label, actual_head):
    parts = []
    if commit == center:
        parts.append(paint(color.GREEN_BOLD, label))
    elif commit == actual_head:
        parts.append(paint(color.GREEN, "HEAD"))
    parts.extend(paint(color.CYAN, name) for name in sorted(names.get(commit, [])))
    return parts


def _commit_text(commit, paint, parts):
    text = paint(color.DIM, commit[:8])
    return text + "  " + ", ".join(parts) if parts else text


def _marker(commit, paint, names, center, actual_head):
    if commit == center:
        return paint(color.GREEN_BOLD, "@")
    if commit == actual_head:
        return paint(color.GREEN, "●")
    return paint(color.CYAN if commit in names else color.DIM, "○")


def with_details(rows, details):
    """Insert commit details into a tuple of graph rows without rebuilding its lanes."""
    if not details:
        return rows
    oid, lines = details
    for index, row in enumerate(rows):
        if row.oid == oid and row.kind == "commit":
            details_rows = tuple(Row(row.detail_prefix + line) for line in lines)
            return rows[:index + 1] + details_rows + rows[index + 1:]
    return rows + tuple(Row(line) for line in lines)


def render_map(names, paint, center, label, center_note=None, *,
               actual_head=None, nearest=(), expanded=(), details=None):
    """Return commit, fold and text rows for one minimap view.

    The oid on a fold row identifies the visible commit directly above that region.
    """
    tips = sorted(set(names) | {center})
    nearest = set(nearest)
    parents, when = _history(tips)
    merge_bases = _merge_bases(tips, parents) - set(tips)
    landmarks = merge_bases | set(tips)
    if actual_head in parents:
        landmarks.add(actual_head)
    expanded = set(expanded).intersection(parents)
    landmarks.update(expanded)

    visible = set(landmarks)
    unfolded = set(expanded)
    if expanded:
        boundaries = _visible_parents(parents, landmarks)
        for anchor in sorted(expanded):
            boundary = boundaries[anchor]
            if boundary and boundary != set(parents[anchor]):
                region = git("rev-list", *_region_args(anchor, boundary)).splitlines()
                unfolded.update(oid for oid in region if oid in parents)
        visible.update(unfolded)
    if details and details[0] in parents:
        visible.add(details[0])

    closest = _visible_parents(parents, visible, unfolded)
    center_line = _center_line(parents, center)

    def sort_key(commit):
        return (-when[commit], commit not in center_line, min(names.get(commit, [commit])), commit)

    above = {commit: sorted(boundary, key=sort_key) for commit, boundary in closest.items()}
    folded = {}
    for commit, boundary in closest.items():
        if boundary and boundary != set(parents[commit]):
            folded[commit] = int(git("rev-list", "--count", *_region_args(commit, boundary))) - 1

    def node_text(commit):
        parts = _labels(commit, paint, names, center, label, actual_head)
        if not parts and commit in merge_bases:
            parts.append(paint(color.DIM, "merge-base"))
        if commit in unfolded and len(parents[commit]) > 1:
            parts.append(paint(color.DIM, "merge"))
        text = _commit_text(commit, paint, parts)
        if commit in nearest:
            text += "  " + paint(color.GREEN, "[nearest]")
        if commit == center and center_note:
            text += "  " + center_note
        return text

    def marker(commit):
        return _marker(commit, paint, names, center, actual_head)

    out = _draw_lanes(above, sort_key, node_text, marker, paint, folded=folded)
    out.append(Row(paint(color.DIM, LEGEND)))
    return list(with_details(tuple(out), details)) if details else out


def render_radius(history, paint, center, label, center_note=None, *,
                  radius=3, actual_head=None, waypoints=(), details=None):
    """Draw the real edges within the radius and mark edges that leave it."""
    neighborhood = history.neighborhood(center, radius)
    names = {}
    destinations = {}
    nearest = None
    for waypoint in waypoints:
        if waypoint.distance is not None and (nearest is None or waypoint.distance < nearest):
            nearest = waypoint.distance
        if waypoint.oid in neighborhood:
            names.setdefault(waypoint.oid, []).extend(waypoint.names)
        elif waypoint.outside is not None:
            edge = _Continuation(waypoint.anchor, waypoint.outside)
            destinations.setdefault(edge, {}).setdefault(waypoint.distance, []).extend(waypoint.names)

    above = {commit: [] for commit in neighborhood}
    for commit in neighborhood:
        for parent in history.parents[commit]:
            if parent in neighborhood:
                above[commit].append(parent)
            else:
                edge = _Continuation(commit, parent)
                above[commit].append(edge)
                above[edge] = []
        for child in history.children[commit]:
            if child not in neighborhood:
                above[_Continuation(commit, child)] = [commit]

    def sort_key(node):
        if isinstance(node, _Continuation):
            return (-history.when[node.outside], radius + 1, node.outside, node.anchor)
        return (-history.when[node], neighborhood[node], node, "")

    def node_text(node):
        if isinstance(node, _Continuation):
            targets = destinations.get(node, {})
            signs = []
            for distance, aliases in sorted(targets.items()):
                unit = "step" if distance == 1 else "steps"
                sign = paint(color.CYAN, ", ".join(sorted(aliases)))
                sign += " " + paint(color.DIM, "(%d %s)" % (distance, unit))
                if distance == nearest:
                    sign += "  " + paint(color.GREEN, "[nearest]")
                signs.append(sign)
            return ", ".join(signs)
        parts = _labels(node, paint, names, center, label, actual_head)
        if len(history.parents[node]) > 1:
            parts.append(paint(color.DIM, "merge"))
        if len(history.children[node]) > 1:
            parts.append(paint(color.DIM, "fork"))
        text = _commit_text(node, paint, parts)
        if node in names and neighborhood[node] == nearest:
            text += "  " + paint(color.GREEN, "[nearest]")
        return text + "  " + center_note if node == center and center_note else text

    def marker(node):
        if isinstance(node, _Continuation):
            return paint(color.DIM, "…")
        return _marker(node, paint, names, center, actual_head)

    for parent_nodes in above.values():
        parent_nodes.sort(key=sort_key)
    out = _draw_lanes(above, sort_key, node_text, marker, paint)
    return list(with_details(tuple(out), details)) if details else out


def _draw_lanes(above, sort_key, node_text, marker, paint, *, folded=None):
    out = []
    lanes = []  # lanes[i] is the commit this lane is heading to, or None if free
    folded = folded or {}

    def prefix(cells, fill=(), width=0):
        """Put a vertical line in each active lane without a supplied glyph."""
        n = max([i for i, c in enumerate(lanes) if c is not None] + [width - 1, *cells]) + 1
        row = ""
        for i in range(n):
            glyph = cells.get(i) or ("│" if i < len(lanes) and lanes[i] else " ")
            row += paint(color.DIM, glyph) if glyph in LINE_GLYPHS else glyph
            row += paint(color.DIM, "─") if i in fill else " "
        return row + " "

    def emit(cells, fill=(), width=0, text="", oid=None, kind="text"):
        text = (prefix(cells, fill, width) + text).rstrip()
        detail_prefix = prefix({}, width=width) if kind == "commit" else ""
        out.append(Row(text, oid, kind, detail_prefix))

    def free_lane(after=-1):
        for i in range(after + 1, len(lanes)):
            if lanes[i] is None:
                return i
        lanes.append(None)
        return len(lanes) - 1

    def draw(commit):
        waiting = [i for i, node in enumerate(lanes) if node == commit]
        if not waiting:
            lane = free_lane()
            lanes[lane] = commit
            waiting = [lane]
        lane, extra = waiting[0], waiting[1:]
        if extra:  # lanes of other children converge onto this node
            cells = {lane: "├", **{j: "┴" for j in extra}, extra[-1]: "╯"}
            for i in range(lane + 1, extra[-1]):
                cells.setdefault(i, "┼" if lanes[i] else "─")
            emit(cells, fill=range(lane, extra[-1]))
            for j in extra:
                lanes[j] = None
        if isinstance(commit, _Continuation):
            emit({lane: marker(commit)}, width=lane + 1, text=node_text(commit))
        else:
            emit({lane: marker(commit)}, width=lane + 1, text=node_text(commit), oid=commit, kind="commit")
        parent_nodes = above[commit]
        lanes[lane] = parent_nodes[0] if parent_nodes else None
        for parent in parent_nodes[1:]:
            joined = parent in lanes
            j = lanes.index(parent) if joined else free_lane(lane)
            lanes[j] = parent
            lo, hi = min(lane, j), max(lane, j)
            cells = {lo: "├", hi: "┤" if joined else "╮"}
            for i in range(lo + 1, hi):
                cells[i] = "┼" if lanes[i] else "─"
            emit(cells, fill=range(lo, hi))
        if folded.get(commit):
            emit({lane: "~"}, text=paint(color.DIM, "(%d)" % folded[commit]), oid=commit, kind="fold")

    pending = dict.fromkeys(above, 0)
    for parent_nodes in above.values():
        for parent in parent_nodes:
            pending[parent] += 1
    ready = [commit for commit, count in pending.items() if count == 0]
    while ready:
        ready.sort(key=sort_key)
        commit = ready.pop(0)
        draw(commit)
        for parent in above[commit]:
            pending[parent] -= 1
            if pending[parent] == 0:
                ready.append(parent)

    return out
