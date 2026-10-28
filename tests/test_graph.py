import re

from git_nearest.cli import main


def graph(capsys, *argv):
    main(["--color", "never", "-g", *argv])
    return re.sub(r"\b[0-9a-f]{8}\b", "H", capsys.readouterr().out).splitlines()


def test_merge_and_fork(forked, capsys):
    assert graph(capsys) == [
        "@  H  HEAD -> work  [clean]",
        "~  (2)",
        "○  H  origin/other",
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
        "○  H  origin/main",
        "~ (n) = n commits folded between",
    ]


def test_head_on_a_remote_tip_shares_a_node(repo, capsys):
    repo.commit(2)
    repo.remote("origin/main")
    assert graph(capsys)[0] == "@  H  HEAD -> main, origin/main  [clean]"


def test_adjacent_nodes_have_no_fold_row(repo, capsys):
    repo.commit(1)
    repo.remote("origin/main")
    repo.commit(1)
    assert graph(capsys) == [
        "@  H  HEAD -> main  [clean]",
        "○  H  origin/main",
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
