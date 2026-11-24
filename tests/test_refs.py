import re

import pytest

from git_nearest import refs


@pytest.mark.parametrize("native", [True, False])
def test_pattern_selects_full_local_and_remote_names_before_limit(forked, native):
    forked.remote("upstream/feat", "feat")
    rows = refs.rank(1, native=native, pattern=re.compile(r"/(heads|remotes/upstream)/feat$"))
    oid = forked.git("rev-parse", "feat")
    assert rows == [
        refs.Row(7, 0, "feat", "refs/heads/feat", oid),
        refs.Row(7, 0, "upstream/feat", "refs/remotes/upstream/feat", oid),
    ]


@pytest.mark.parametrize("native", [True, False])
def test_limit_counts_distinct_tips_and_keeps_their_matching_aliases(forked, native):
    forked.remote("origin/other-alias", "origin/other")
    forked.remote("origin/hidden", "origin/other")
    rows = refs.rank(2, native=native, pattern=re.compile(r"^refs/remotes/origin/(other.*|feat|main)$"))
    assert [row.ref for row in rows] == ["origin/other", "origin/other-alias", "origin/feat"]
    assert rows[0].oid == rows[1].oid
    assert rows[0].oid != rows[2].oid


@pytest.mark.parametrize("native", [True, False])
def test_symbolic_refs_are_skipped_but_branch_names_ending_in_head_are_valid(forked, native):
    forked.remote("origin/feature/HEAD")
    forked.git("symbolic-ref", "refs/remotes/origin/shortcut", "refs/remotes/origin/feature/HEAD")
    rows = refs.rank(1, native=native)
    assert [row.ref for row in rows] == ["origin/feature/HEAD"]


@pytest.mark.parametrize("native", [True, False])
def test_skip_removes_selected_ref_and_leaves_other_refs_at_its_tip(forked, native):
    forked.git("branch", "work-alias")
    forked.remote("origin/work")
    rows = refs.rank(1, skip="refs/heads/work", native=native, pattern=re.compile(r"^refs/"))
    assert [row.full_ref for row in rows] == ["refs/remotes/origin/work", "refs/heads/work-alias"]
    assert all(row.ahead == row.behind == 0 for row in rows)


def test_no_matching_refs_skips_counting(forked, monkeypatch):
    git = refs.git

    def enumerate_refs_only(*args, **kwargs):
        assert args[0] == "for-each-ref"
        assert all("ahead-behind" not in arg for arg in args)
        return git(*args, **kwargs)

    monkeypatch.setattr(refs, "git", enumerate_refs_only)
    assert refs.rank(5, pattern=re.compile(r"^refs/tags/")) == []
