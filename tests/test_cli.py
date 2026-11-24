import re

import pytest

from git_nearest.cli import main


def run(capsys, *argv):
    code = main(["--color", "never", *argv])
    out = capsys.readouterr()
    return code, re.sub(r"\b[0-9a-f]{8}\b", "H", out.out), out.err


def test_defaults_to_graph_with_nearest_label(forked, capsys):
    code, out, err = run(capsys)
    assert code == 0
    assert not err
    assert out.splitlines()[0] == "@  H  HEAD -> work  [clean]"
    assert "origin/other  [nearest]" in out
    assert "origin/feat" in out
    assert "origin/main" in out
    assert "↑" not in out
    assert "↓" not in out


def test_limit_counts_positions(forked, capsys):
    forked.remote("upstream/other", "refs/remotes/origin/other")
    code, out, _ = run(capsys, "2")
    assert code == 0
    assert "origin/other" in out
    assert "upstream/other" in out
    assert "origin/feat" in out
    assert "origin/main" not in out


def test_filter_matches_full_ref_names_before_limit(forked, capsys):
    code, out, _ = run(capsys, "1", "--match", "^refs/remotes/origin/main$")
    assert code == 0
    assert "origin/main  [nearest]" in out
    assert "origin/other" not in out


def test_filter_can_show_local_branches_without_self(forked, capsys):
    code, out, _ = run(capsys, "--match", "^refs/heads/")
    assert code == 0
    assert "HEAD -> work" in out
    assert "main  [nearest]" in out
    assert "feat" in out
    assert "origin/" not in out
    assert "[nearest], work" not in out


def test_only_symbolic_remote_refs_are_skipped(forked, capsys):
    forked.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    forked.remote("origin/release/HEAD")
    _, out, _ = run(capsys, "--no-status")
    assert "origin/HEAD" not in out
    assert "origin/release/HEAD" in out
    assert "[clean]" not in out


def test_no_remote_refs_shows_center(repo, capsys):
    repo.commit()
    code, out, err = run(capsys)
    assert code == 0
    assert not err
    assert "HEAD -> main" in out
    assert "No remote branches found" in out


def test_empty_filter_has_clear_message(forked, capsys):
    code, out, err = run(capsys, "--match", "^refs/heads/absent$")
    assert code == 0
    assert not err
    assert "HEAD -> work" in out
    assert "No branches match the filter." in out


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


def test_interactive_requires_terminal(forked, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        main(["-i"])
    assert "requires an interactive terminal" in capsys.readouterr().err


def test_color_always_emits_escapes(forked, capsys):
    main(["--color", "always"])
    assert "\033[" in capsys.readouterr().out


def test_branch_measures_from_another_rev(forked, capsys):
    _, out, _ = run(capsys, "-b", "main")
    assert any(line.startswith("@") and "H  main" in line for line in out.splitlines())
    assert "origin/other  [nearest]" in out
    assert "HEAD -> work (outside map)" in out
    assert "[clean]" not in out
    assert forked.git("symbolic-ref", "--short", "HEAD") == "work"


def test_branch_skips_itself_when_remote(forked, capsys):
    _, out, _ = run(capsys, "-b", "origin/other")
    assert out.count("origin/other") == 1
    assert any(line.startswith("@") and "H  origin/other" in line for line in out.splitlines())


def test_expand_and_details_from_command_line(forked, capsys):
    previous = forked.git("rev-parse", "HEAD^")
    parent = forked.git("rev-parse", "HEAD^^")
    code = main(["--color", "never", "--expand", "HEAD", "--details", "HEAD^"])
    out = capsys.readouterr().out
    assert code == 0
    assert previous[:8] in out
    assert "Commit " + previous in out
    assert "Author t" in out
    assert "Parents " + parent in out


def test_bad_branch(forked, capsys):
    code, _, err = run(capsys, "-b", "nope")
    assert code == 1
    assert "nope" in err


def test_bad_regex(forked, capsys):
    code, _, err = run(capsys, "--match", "[")
    assert code == 1
    assert "invalid branch regex" in err
