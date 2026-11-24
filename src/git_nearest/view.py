"""Shared options and a repository snapshot for exploring a radius view."""
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import lru_cache
import re
from threading import Event
from typing import NamedTuple, Optional, Tuple

from . import color, graph, refs, status
from .gitutil import GitError, git
from .navigation import History


@dataclass(frozen=True)
class Options:
    limit: int = 5
    rev: str = "HEAD"
    pattern: Optional[str] = None
    expanded: Tuple[str, ...] = ()
    details: Optional[str] = None
    radius: Optional[int] = None


@dataclass(frozen=True)
class View:
    state: Options
    center: str
    rows: Tuple[graph.Row, ...]
    parents: Tuple[str, ...] = ()
    children: Tuple[str, ...] = ()
    pending: bool = False


def resolve(rev):
    args = ("rev-parse", "--verify", "--end-of-options", rev + "^{commit}")
    if rev == "HEAD":
        return git(*args)
    oid = git(*args, check=False)
    if oid:
        return oid
    raise GitError("not a valid branch or commit: " + one_line(rev))


def symbolic(rev):
    return git("rev-parse", "--verify", "--symbolic-full-name", "--end-of-options", rev, check=False)


def one_line(text):
    return "".join(c if c.isprintable() else " " for c in text)


def head_label():
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False)
    return "HEAD -> " + branch if branch else "HEAD (detached)"


def commit_details(oid):
    subject, author, date, parents = git(
        "show", "-s", "--format=%s%x00%an%x00%aI%x00%P", oid, strip=False
    ).rstrip("\n").split("\0")
    return (
        "Commit " + oid,
        "  " + one_line(subject),
        "  Author " + one_line(author),
        "  Date " + date,
        "  Parents " + (parents or "(root)"),
    )


def compile_pattern(pattern):
    try:
        return re.compile(pattern) if pattern is not None else None
    except re.error as exc:
        raise GitError("invalid branch regex: " + one_line(str(exc))) from exc


def branches_message(pattern):
    return ("No branches match the filter." if pattern is not None else
            "No remote branches found (try git fetch or --match '^refs/heads/').")


class _RouteKey(NamedTuple):
    center: str
    radius: int
    pattern: Optional[str]
    skip: str
    limit: int


class RadiusSession:
    """Build topology once and answer view edits from the local snapshot."""

    def __init__(self, state, paint, check_tree):
        compile_pattern(state.pattern)
        self.paint = paint
        start = resolve(state.rev)
        self.head = start if state.rev == "HEAD" else git(
            "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}", check=False
        )
        self.head_name = head_label() if self.head else ""
        self.check_tree = check_tree
        self.head_note = None
        self.refs = refs.branch_tips()
        self.revisions = {state.rev: (start, symbolic(state.rev))}
        if self.head and state.rev != "HEAD":
            self.revisions["HEAD"] = (self.head, symbolic("HEAD"))
        tips = {start, *self.refs.values()}
        if self.head:
            tips.add(self.head)
        self.history = History(tips)
        self._names = lru_cache(maxsize=12)(self._candidate_names)
        self._details = lru_cache(maxsize=128)(commit_details)
        self._layouts = OrderedDict()
        self._routes = OrderedDict()
        self._executor = None
        self._job = None

    def _candidate_names(self, pattern, skip):
        regex = compile_pattern(pattern)
        candidates = [
            (ref, oid, ref.split("/", 2)[2])
            for ref, oid in self.refs.items()
            if ref != skip and (regex.search(ref) if regex is not None else ref.startswith(refs.REMOTES))
        ]
        counts = Counter(label for _, _, label in candidates)
        names = {}
        for ref, oid, label in candidates:
            names.setdefault(oid, []).append(ref if counts[label] > 1 else label)
        return names

    def _revision(self, rev):
        if rev in self.history.parents:
            return rev, ""
        if rev not in self.revisions:
            self.revisions[rev] = (resolve(rev), symbolic(rev))
        return self.revisions[rev]

    def _key(self, state):
        center, skip = self._revision(state.rev)
        return _RouteKey(center, state.radius, state.pattern, skip, state.limit)

    def _cancel_route(self):
        if self._job is not None:
            _, cancel, future = self._job
            cancel.set()
            future.cancel()
            self._job = None

    def _store_route(self, key, waypoints):
        self._routes[key] = waypoints
        self._routes.move_to_end(key)
        if len(self._routes) > 32:
            self._routes.popitem(last=False)
        return waypoints

    def _waypoints(self, key, names, wait):
        if self._job and self._job[0] != key:
            self._cancel_route()
        if key in self._routes:
            self._routes.move_to_end(key)
            return self._routes[key]
        if not names:
            return ()
        if self._job:
            _, _, future = self._job
            if wait or future.done():
                self._job = None
                return self._store_route(key, future.result())
        if wait:
            return self._store_route(key, self.history.waypoints(key.center, key.radius, names, key.limit))
        return None

    def load(self, state, *, wait=False):
        key = self._key(state)
        names = self._names(state.pattern, key.skip)
        center = key.center
        if center not in self.history.parents:
            self._cancel_route()
            self.history.add(center)
            self._routes.clear()
            self._layouts.clear()
        waypoints = self._waypoints(key, names, wait)
        detail_oid = self._revision(state.details)[0] if state.details is not None else None
        state = replace(state, details=detail_oid)
        details = (detail_oid, self._details(detail_oid)) if detail_oid else None
        label = self.head_name if center == self.head else one_line(state.rev)
        if state.rev == center and center != self.head:
            label = ""
        if center == self.head and self.check_tree and self.head_note is None:
            self.head_note = status.describe(status.read(), self.paint)
        note = self.head_note if center == self.head else None

        layout_key = center, label, state.radius, waypoints
        if layout_key not in self._layouts:
            self._layouts[layout_key] = tuple(graph.render_radius(
                self.history, self.paint, center, label, note, radius=state.radius,
                actual_head=self.head, waypoints=waypoints or (),
            ))
            if len(self._layouts) > 16:
                self._layouts.popitem(last=False)
        else:
            self._layouts.move_to_end(layout_key)
        rows = graph.with_details(self._layouts[layout_key], details)
        if not names:
            rows += (graph.Row(self.paint(color.DIM, branches_message(state.pattern))),)
        elif waypoints == ():
            rows += (graph.Row(self.paint(color.DIM, "No route to a matching branch in local history.")),)

        return View(state, center, rows, self.history.parents[center], self.history.children[center],
                    pending=waypoints is None)

    def refresh(self, view):
        if not view.pending:
            return view
        key = self._key(view.state)
        if self._job is not None:
            if self._job[0] == key:
                return self.load(view.state) if self._job[2].done() else view
            self._cancel_route()
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1)
        cancel = Event()
        future = self._executor.submit(
            self.history.waypoints, key.center, key.radius, self._names(key.pattern, key.skip),
            key.limit, cancel.is_set,
        )
        self._job = (key, cancel, future)
        return view

    def close(self):
        self._cancel_route()
        if self._executor is not None:
            self._executor.shutdown()
