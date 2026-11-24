import re

from git_nearest.cli import main
from git_nearest.color import Painter
from git_nearest.graph import render_map


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
