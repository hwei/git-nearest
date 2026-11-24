import re
from types import SimpleNamespace

from git_nearest.cli import main
from git_nearest.color import Painter
from git_nearest.graph import render_map, render_radius, with_details


def graph(capsys, *argv):
    main(["--color", "never", *argv])
    return re.sub(r"\b[0-9a-f]{8}\b", "H", capsys.readouterr().out).splitlines()


def test_merge_and_fork(forked, capsys):
    assert graph(capsys) == [
        "@  H  HEAD -> work  [clean]",
        "~  (2)",
        "○  H  origin/other  [nearest]",
        "├─╮",
        "~ │  (1)",
        "○ │  H  origin/feat",
        "~ │  (2)",
        "│ ○  H  origin/main",
        "│ ~  (1)",
        "├─╯",
        "○  H  merge-base",
        "~ (n) = n commits folded between",
    ]


def test_linear_history_has_no_lanes(repo, capsys):
    repo.commit(3)
    repo.remote("origin/main")
    repo.commit(4)
    assert graph(capsys) == [
        "@  H  HEAD -> main  [clean]",
        "~  (3)",
        "○  H  origin/main  [nearest]",
        "~ (n) = n commits folded between",
    ]


def test_head_on_a_remote_tip_shares_a_node(repo, capsys):
    repo.commit(2)
    repo.remote("origin/main")
    assert graph(capsys)[0] == "@  H  HEAD -> main, origin/main  [nearest]  [clean]"


def test_adjacent_nodes_have_no_fold_row(repo, capsys):
    repo.commit(1)
    repo.remote("origin/main")
    repo.commit(1)
    assert graph(capsys) == [
        "@  H  HEAD -> main  [clean]",
        "○  H  origin/main  [nearest]",
        "~ (n) = n commits folded between",
    ]


def test_detached_head(repo, capsys):
    repo.commit(2)
    repo.remote("origin/main")
    repo.git("checkout", "-q", "--detach")
    repo.commit(1)
    assert graph(capsys)[0] == "@  H  HEAD (detached)  [clean]"


def test_unrelated_histories_do_not_crash(repo, capsys):
    repo.commit(2)
    repo.git("checkout", "-q", "--orphan", "other")
    repo.commit(2)
    repo.remote("origin/main", "main")
    lines = graph(capsys)
    assert any("origin/main" in line for line in lines)
    assert any("HEAD -> other" in line for line in lines)


def test_newest_first_among_branches(repo, capsys, monkeypatch):
    def commit_at(ts):
        monkeypatch.setenv("GIT_COMMITTER_DATE", "%d +0000" % ts)
        repo.commit()

    commit_at(1000000000)
    repo.git("checkout", "-q", "-b", "side")
    commit_at(1000000100)
    repo.remote("origin/a-old")  # sorts first by name but is older
    repo.git("checkout", "-q", "main")
    commit_at(1000000200)
    repo.remote("origin/z-new")
    commit_at(1000000300)
    lines = graph(capsys)
    refs = [word for line in lines for word in line.split() if word.startswith("origin/")]
    assert refs == ["origin/z-new", "origin/a-old"]


def test_expanding_fold_restores_merge_topology(repo):
    repo.commit()
    base = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "-b", "side")
    repo.commit()
    side = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "main")
    repo.commit()
    main_parent = repo.git("rev-parse", "HEAD")
    repo.git("merge", "-q", "--no-ff", "side", "-m", "merge side")
    merge = repo.git("rev-parse", "HEAD")
    repo.commit()
    center = repo.git("rev-parse", "HEAD")

    names = {base: ["origin/main"]}
    paint = Painter(False)
    collapsed = render_map(names, paint, center, "HEAD")
    assert [(row.oid, row.text) for row in collapsed if row.kind == "fold"] == [(center, "~  (3)")]

    expanded = render_map(names, paint, center, "HEAD", expanded=[center])
    nodes = [row.oid for row in expanded if row.kind == "commit"]
    assert nodes[0:2] == [center, merge]
    assert set(nodes[2:4]) == {main_parent, side}
    assert nodes[4:] == [base]
    assert any(row.oid == merge and row.text.endswith("merge") for row in expanded)
    assert any(row.text == "├─╮" for row in expanded)
    assert not any(row.kind == "fold" for row in expanded)

    with_details = render_map(names, paint, center, "HEAD", expanded=[center],
                              details=(merge, ["Test details"]))
    assert [row.oid for row in with_details if row.kind == "commit"] == nodes
    assert not any(row.kind == "fold" for row in with_details)


def test_expanding_one_region_leaves_another_folded(repo):
    repo.commit()
    base = repo.git("rev-parse", "HEAD")
    repo.commit(2)
    middle = repo.git("rev-parse", "HEAD")
    repo.commit()
    intermediate = repo.git("rev-parse", "HEAD")
    repo.commit()
    center = repo.git("rev-parse", "HEAD")

    names = {base: ["origin/base"], middle: ["origin/middle"]}
    rows = render_map(names, Painter(False), center, "HEAD", expanded=[center])
    assert [(row.oid, row.text) for row in rows if row.kind == "fold"] == [(middle, "~  (1)")]
    assert [row.oid for row in rows if row.kind == "commit"] == [center, intermediate, middle, base]


def test_details_and_head_mark_a_commit_inside_the_neighborhood(repo):
    repo.commit()
    base = repo.git("rev-parse", "HEAD")
    repo.commit()
    actual_head = repo.git("rev-parse", "HEAD")
    repo.commit()
    center = repo.git("rev-parse", "HEAD")
    details = (actual_head, ["Test details"])

    rows = render_map({base: ["origin/main"]}, Painter(False), center, "chosen center",
                      actual_head=actual_head, details=details)

    assert rows[0].text.startswith("@ ")
    assert rows[1].oid == actual_head
    assert rows[1].text.startswith("● ")
    assert rows[2].text.strip() == "│  Test details"


def radius_history(parents, distances):
    children = {commit: [] for commit in parents}
    for commit, parent_ids in parents.items():
        for parent in parent_ids:
            children[parent].append(commit)
    return SimpleNamespace(
        parents=parents,
        children=children,
        when={commit: i for i, commit in enumerate(parents)},
        neighborhood=lambda center, radius: {c: d for c, d in distances.items() if d <= radius},
    )


def waypoint(oid, distance, *names, anchor=None, outside=None):
    return SimpleNamespace(oid=oid, names=names, distance=distance, anchor=anchor, outside=outside)


def test_radius_keeps_the_merge_and_places_waypoints_on_the_cut_edge():
    history = radius_history(
        {"a": [], "b": ["a"], "c": ["b"], "d": ["b"], "e": ["c", "d"], "f": ["e"]},
        {"e": 0, "c": 1, "d": 1, "f": 1, "b": 2, "a": 3},
    )
    waypoints = [
        waypoint("a", 3, "origin/main", anchor="c", outside="b"),
        waypoint("f", 1, "origin/next"),
    ]
    rows = render_radius(history, Painter(False), "e", "view center", radius=1,
                         actual_head="d", waypoints=waypoints)
    commits = [row for row in rows if row.kind == "commit"]
    assert {row.oid for row in commits} == {"c", "d", "e", "f"}
    assert "merge" in next(row.text for row in commits if row.oid == "e")
    assert "●" in next(row.text for row in commits if row.oid == "d")
    assert "origin/next  [nearest]" in next(row.text for row in commits if row.oid == "f")
    assert any("├─╮" in row.text for row in rows)
    assert sum("…" in row.text for row in rows) == 2
    sign = next(row for row in rows if "origin/main (3 steps)" in row.text)
    assert "…" in sign.text
    assert sign.kind == "text" and sign.oid is None


def test_zero_radius_retains_boundary_layout_and_groups_offscreen_aliases():
    history = radius_history(
        {"a": [], "b": ["a"], "c": ["b"], "d": ["c"]},
        {"b": 0, "a": 1, "c": 1, "d": 2},
    )
    paint = Painter(False)
    initial = render_radius(history, paint, "b", "HEAD", radius=0)
    waypoints = [
        waypoint("a", 1, "upstream/main", "origin/main", anchor="b", outside="a"),
        waypoint("d", 2, "origin/future", anchor="b", outside="c"),
    ]
    updated = render_radius(history, paint, "b", "HEAD", radius=0, waypoints=waypoints,
                            details=("a", ["Outside details"]))
    assert [(row.text[0], row.kind, row.oid) for row in updated[:-1]] == [
        (row.text[0], row.kind, row.oid) for row in initial
    ] == [("…", "text", None), ("@", "commit", "b"), ("…", "text", None)]
    assert updated[0].text.endswith("origin/future (2 steps)")
    assert updated[2].text.endswith("origin/main, upstream/main (1 step)  [nearest]")
    assert updated[3].text == "Outside details"

    with_center_details = with_details(tuple(initial), ("b", ["Center details"]))
    assert with_center_details[2].text == "│  Center details"
    assert with_center_details[:2] + with_center_details[3:] == tuple(initial)
