import re

import pytest

from git_nearest import refs
from git_nearest.cli import main


def run(capsys, *argv):
    code = main(["--color", "never", *argv])
    out = capsys.readouterr()
    return code, re.sub(r"\b[0-9a-f]{8}\b", "H", out.out), out.err


def test_table_orders_by_ahead_then_behind(forked, capsys):
    code, out, _ = run(capsys)
    assert code == 0
    assert out.splitlines() == [
        "@  HEAD -> work  [clean]",
        "↑3 ↓0  origin/other  H",
        "↑7 ↓0  origin/feat   H",
        "↑8 ↓0  origin/main   H",
    ]


def test_limit(forked, capsys):
    _, out, _ = run(capsys, "1")
    assert out.splitlines() == ["@  HEAD -> work  [clean]", "↑3 ↓0  origin/other  H"]


def test_behind_is_counted(repo, capsys):
    repo.commit(2)
    repo.git("checkout", "-q", "-b", "side")
    repo.commit(2)
    repo.git("checkout", "-q", "main")
    repo.commit(1)
    repo.remote("origin/main")
    repo.git("checkout", "-q", "side")
    _, out, _ = run(capsys)
    assert out.splitlines()[1] == "↑2 ↓1  origin/main  H"


def test_fallback_matches_native(forked):
    assert refs.rank(10, native=False) == refs.rank(10, native=True)


def test_origin_head_is_skipped(forked, capsys):
    forked.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    _, out, _ = run(capsys, "--no-status")
    assert "HEAD" not in out


def test_no_remote_refs(repo, capsys):
    repo.commit()
    code, _, err = run(capsys)
    assert code == 1
    assert "no remote branches" in err


def test_no_commits(repo, capsys):
    code, _, err = run(capsys)
    assert code == 1
    assert err.startswith("git-nearest:")


def test_not_a_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    code, _, err = run(capsys)
    assert code == 1
    assert "not a git repository" in err


def test_bad_limit(forked):
    with pytest.raises(SystemExit):
        main(["0"])


def test_color_always_emits_escapes(forked, capsys):
    main(["--color", "always"])
    assert "\033[" in capsys.readouterr().out


def test_branch_measures_from_another_rev(forked, capsys):
    _, out, _ = run(capsys, "-b", "main")
    assert out.splitlines() == [
        "@  main",
        "↑1 ↓0  origin/other  H",
        "↑5 ↓0  origin/feat   H",
        "↑6 ↓0  origin/main   H",
    ]


def test_branch_skips_itself_when_remote(forked, capsys):
    _, out, _ = run(capsys, "-b", "origin/other")
    assert "origin/other" not in out.splitlines()[1]
    assert out.splitlines()[0] == "@  origin/other"


def test_branch_graph_is_labelled(forked, capsys):
    _, out, _ = run(capsys, "-g", "-b", "feat")
    assert any(l.startswith("@") and l.endswith("H  feat, origin/feat") for l in out.splitlines())


def test_bad_branch(forked, capsys):
    code, _, err = run(capsys, "-b", "nope")
    assert code == 1
    assert "nope" in err
