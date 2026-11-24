from dataclasses import replace
from threading import Event

from git_nearest import graph, navigation, refs, status, view
from git_nearest.color import Painter


def test_details_and_walking_reuse_the_history_and_layout(forked, monkeypatch):
    calls = []
    git = view.git

    def record(*args, **kwargs):
        calls.append(args[0])
        return git(*args, **kwargs)

    for module in (view, navigation, refs, status):
        monkeypatch.setattr(module, "git", record)

    options = view.Options(radius=3)
    session = view.RadiusSession(options, Painter(False), check_tree=True)
    try:
        initial = session.load(options, wait=True)
        assert initial.parents
        render_calls = []
        render = graph.render_radius

        def render_record(*args, **kwargs):
            render_calls.append(args[2])
            return render(*args, **kwargs)

        monkeypatch.setattr(graph, "render_radius", render_record)
        calls.clear()
        with_details = replace(options, details=initial.center)
        first = session.load(with_details)
        assert any("Author t" in row.text for row in first.rows)
        assert calls == ["show"]

        calls.clear()
        assert session.load(options).rows == initial.rows
        assert session.load(with_details).rows == first.rows
        assert not calls
        assert not render_calls

        moved = session.load(replace(options, rev=initial.parents[0]))
        assert moved.center == initial.parents[0]
        assert initial.center in moved.children
        assert not calls
        assert render_calls == [moved.center]
    finally:
        session.close()


def test_obsolete_waypoint_search_is_cancelled(forked, monkeypatch):
    options = view.Options(radius=1)
    session = view.RadiusSession(options, Painter(False), check_tree=False)
    started = Event()
    release = Event()
    cancelled = []
    try:
        initial = session.load(options)
        assert initial.pending
        search = session.history.waypoints

        def delayed(center, radius, names, limit, cancel=None):
            if center == initial.center:
                started.set()
                assert release.wait(timeout=5)
                cancelled.append(cancel())
            return search(center, radius, names, limit, cancel)

        monkeypatch.setattr(session.history, "waypoints", delayed)
        assert session.refresh(initial) is initial
        assert started.wait(timeout=5)
        moved = session.load(replace(options, rev=initial.parents[0]))
        assert moved.pending
        release.set()
        assert session.refresh(moved) is moved
        complete = session.load(moved.state, wait=True)
        assert not complete.pending
        assert complete.center == moved.center
        assert cancelled == [True]
        assert any("origin/other" in row.text for row in complete.rows)
    finally:
        release.set()
        session.close()
