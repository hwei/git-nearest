import re

from git_nearest import status
from git_nearest.color import Painter
from git_nearest.cli import main


def head_line(capsys, *argv):
    main(["--color", "never", *argv])
    return capsys.readouterr().out.splitlines()[0]


def write(repo, name, text="x"):
    with open(repo.path + "/" + name, "w") as f:
        f.write(text)


def tracked(repo, name):
    write(repo, name)
    repo.git("add", name)
    repo.git("commit", "-q", "-m", "add " + name)


def test_clean(forked):
    assert status.read() == status.Counts(0, 0, 0, 0)


def test_counts_each_kind(forked):
    tracked(forked, "a.txt")
    tracked(forked, "b.txt")
    write(forked, "a.txt", "changed")        # modified
    write(forked, "b.txt", "changed")
    forked.git("add", "b.txt")               # staged
    write(forked, "new.txt")                 # untracked
    assert status.read() == status.Counts(staged=1, modified=1, untracked=1, conflicted=0)


def test_file_both_staged_and_modified_counts_in_both(forked):
    tracked(forked, "a.txt")
    write(forked, "a.txt", "one")
    forked.git("add", "a.txt")
    write(forked, "a.txt", "two")
    assert status.read() == status.Counts(staged=1, modified=1, untracked=0, conflicted=0)


def test_ignored_files_are_not_counted(forked):
    tracked(forked, ".gitignore")
    write(forked, ".gitignore", "*.log\n")
    forked.git("add", ".gitignore")
    forked.git("commit", "-q", "-m", "ignore")
    write(forked, "x.log")
    assert status.read() == status.Counts(0, 0, 0, 0)


def test_conflict(repo):
    tracked(repo, "f.txt")
    repo.git("checkout", "-q", "-b", "side")
    write(repo, "f.txt", "side")
    repo.git("commit", "-qam", "side")
    repo.git("checkout", "-q", "main")
    write(repo, "f.txt", "main")
    repo.git("commit", "-qam", "main")
    try:
        repo.git("merge", "side")
    except Exception:
        pass
    assert status.read().conflicted == 1


def test_header_line_in_table(forked, capsys):
    tracked(forked, "a.txt")
    write(forked, "a.txt", "changed")
    write(forked, "new.txt")
    assert head_line(capsys) == "@  HEAD -> work  [1 modified, 1 untracked]"


def test_graph_marks_head_node(forked, capsys):
    write(forked, "new.txt")
    main(["--color", "never", "-g"])
    first = capsys.readouterr().out.splitlines()[0]
    assert re.sub(r"\b[0-9a-f]{8}\b", "H", first) == "@  H  HEAD -> work  [1 untracked]"


def test_no_status_skips_it(forked, capsys):
    main(["--color", "never", "--no-status"])
    assert capsys.readouterr().out.splitlines()[0].startswith("↑")


def test_describe_colors():
    p = Painter(True)
    assert "\033[32m[clean]" in status.describe(status.Counts(0, 0, 0, 0), p)
    assert "\033[33m" in status.describe(status.Counts(0, 1, 0, 0), p)
    assert "\033[31m" in status.describe(status.Counts(0, 0, 0, 1), p)
