import pytest

from git_nearest.navigation import History, Waypoint


@pytest.fixture
def merged(repo):
    repo.commit()
    base = repo.git("rev-parse", "HEAD")
    repo.commit()
    left = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "-b", "side", base)
    repo.commit()
    right = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "side", "-m", "merge side")
    merge = repo.git("rev-parse", "HEAD")
    repo.commit()
    head = repo.git("rev-parse", "HEAD")
    return base, left, right, merge, head


def test_neighborhood_follows_real_parent_and_child_edges(merged):
    base, left, right, merge, head = merged
    history = History([head])
    assert history.parents[merge] == (left, right)
    assert history.children[base] == tuple(sorted((left, right)))
    assert list(history.neighborhood(left, 2).items()) == [
        (left, 0), (base, 1), (merge, 1), (right, 2), (head, 2),
    ]


def test_waypoints_keep_aliases_and_choose_one_path_at_the_boundary(merged):
    base, left, right, merge, head = merged
    history = History([head])
    names = {head: ["detail", "alpha"], right: ["beta"], merge: ["merge"]}
    assert history.waypoints(left, 1, names, 2) == (
        Waypoint(merge, ("merge",), 1, None, None),
        Waypoint(head, ("alpha", "detail"), 2, merge, head),
    )
    assert history.waypoints(left, 1, names, 3)[-1] == (
        Waypoint(right, ("beta",), 2, base, right)
    )


def test_distant_waypoint_uses_shortest_path_through_a_merge(repo):
    repo.commit()
    base = repo.git("rev-parse", "HEAD")
    repo.commit(5)
    left = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "-b", "side", base)
    repo.commit(5)
    right = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "side", "-m", "merge side")
    merge = repo.git("rev-parse", "HEAD")
    history = History([merge])
    assert history.waypoints(left, 0, {right: ["side"]}, 1) == (
        Waypoint(right, ("side",), 2, left, merge),
    )


def test_history_add_reuses_indexed_ancestry_and_updates_child_edges(repo):
    repo.commit(2)
    old_tip = repo.git("rev-parse", "HEAD")
    history = History([old_tip])
    previous_children = history.children
    repo.git("checkout", "-q", "--detach")
    repo.commit(2)
    new_tip = repo.git("rev-parse", "HEAD")
    new_parent = repo.git("rev-parse", "HEAD^")
    history.add(new_tip)
    assert list(history.neighborhood(old_tip, 2))[:3] == [
        old_tip, repo.git("rev-parse", "main^"), new_parent,
    ]
    assert history.parents[new_parent] == (old_tip,)
    assert history.children[old_tip] == (new_parent,)
    assert previous_children[old_tip] == ()


def test_disconnected_and_cancelled_signs_are_excluded(repo):
    repo.commit(3)
    center = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "--orphan", "other")
    repo.commit()
    other = repo.git("rev-parse", "HEAD")
    history = History([center, other])
    names = {center: ["main"], other: ["other"]}
    checks = iter([False, False, True])
    assert history.waypoints(center, 1, names, 2) == (Waypoint(center, ("main",), 0, None, None),)
    assert history.waypoints(center, 1, names, 2, cancelled=lambda: next(checks)) == ()
