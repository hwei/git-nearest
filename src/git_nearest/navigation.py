"""Index known commit edges and find routes through the local Git history."""
from collections import deque, namedtuple
from itertools import chain
from sys import intern

from .gitutil import git

Waypoint = namedtuple("Waypoint", "oid names distance anchor outside")
_Index = namedtuple("_Index", "tips parents children when")


def _read(tips, exclude=()):
    parents = {}
    when = {}
    if not tips:
        return parents, when
    revisions = "\n".join(chain(tips, ("^" + oid for oid in exclude))) + "\n"
    out = git("rev-list", "--timestamp", "--parents", "--topo-order", "--stdin", input=revisions)
    for line in out.splitlines():
        timestamp, oid, *parent_ids = line.split()
        oid = intern(oid)
        parents[oid] = tuple(map(intern, parent_ids))
        when[oid] = int(timestamp)
    return parents, when


def _children(parents, when, existing=None):
    additions = {}
    for oid, parent_ids in parents.items():
        for parent in parent_ids:
            additions.setdefault(parent, []).append(oid)
    children = additions if existing is None else existing.copy()
    for oid, new in additions.items():
        old = () if existing is None else existing.get(oid, ())
        children[oid] = tuple(sorted(chain(old, new), key=lambda child: (-when[child], child)))
    for oid in parents:
        children.setdefault(oid, ())
    return children


def _neighbors(index, oid):
    return chain(index.parents[oid], index.children[oid])


class History:
    """The commit graph reachable from a snapshot of branch tips and observation points."""

    def __init__(self, tips):
        tips = tuple(sorted(set(tips)))
        parents, when = _read(tips)
        self._index = _Index(tips, parents, _children(parents, when), when)

    @property
    def parents(self):
        return self._index.parents

    @property
    def children(self):
        return self._index.children

    @property
    def when(self):
        return self._index.when

    def add(self, oid):
        """Add the ancestry of a valid commit reached by a direct jump."""
        previous = self._index
        if oid in previous.parents:
            return
        tips = (*previous.tips, oid)
        additions, dates = _read((oid,), previous.tips)
        if oid not in additions or any(
            parent not in previous.parents and parent not in additions
            for parent_ids in additions.values() for parent in parent_ids
        ):
            # A shallow repository can gain ancestors after the snapshot was made.
            parents, when = _read(tips)
            self._index = _Index(tips, parents, _children(parents, when), when)
            return
        parents = {**previous.parents, **additions}
        when = {**previous.when, **dates}
        children = _children(additions, when, previous.children)
        self._index = _Index(tips, parents, children, when)

    def neighborhood(self, center, radius):
        """Return commits within radius parent or child hops, closest first."""
        index = self._index
        distances = {center: 0}
        pending = deque([center])
        while pending:
            oid = pending.popleft()
            distance = distances[oid]
            if distance >= radius:
                break
            for neighbor in _neighbors(index, oid):
                if neighbor not in distances:
                    distances[neighbor] = distance + 1
                    pending.append(neighbor)
        return distances

    def waypoints(self, center, radius, names, limit, cancelled=None):
        """Find the closest reachable named tips, including the boundary of each route."""
        index = self._index
        limit = min(limit, len(names.keys() & index.parents.keys()))
        if limit <= 0:
            return ()
        frontier = [(center, None, None)]
        visited = {center}
        distance = 0
        found = []
        while frontier:
            matches = []
            for oid, anchor, outside in frontier:
                if cancelled is not None and cancelled():
                    return ()
                if oid in names:
                    matches.append(Waypoint(oid, tuple(sorted(names[oid])), distance, anchor, outside))
            matches.sort(key=lambda route: (route.names, route.oid))
            found.extend(matches[:limit - len(found)])
            if len(found) == limit:
                break

            following = []
            for oid, anchor, outside in frontier:
                if cancelled is not None and cancelled():
                    return ()
                for neighbor in _neighbors(index, oid):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        if distance == radius:
                            following.append((neighbor, oid, neighbor))
                        else:
                            following.append((neighbor, anchor, outside))
            frontier = following
            distance += 1
        return () if cancelled is not None and cancelled() else tuple(found)
