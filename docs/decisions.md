# Decisions

Settled. Do not reopen without the user asking. Add new entries at the bottom: what, and why.

- **Name `git-nearest`.** Works as `git nearest` via the `git-<name>` convention. Was free on PyPI and
  GitHub when checked; re-check right before publishing.
- **Pure standard library, Python >= 3.8.** Zero install friction for a small git helper.
- **MIT license.** Author `hwei <814065+hwei@users.noreply.github.com>` in `pyproject.toml`, `LICENSE`
  and commits. No other email anywhere in the repo.
- **Output glyphs:** HEAD is `@`, fold counts are `(n)`, folded rows use `~`. Matches `jj log` closely
  enough to be familiar.
- **Ranking is a heuristic** (fewest ahead, then fewest behind). git has no notion of a parent branch;
  the README says so rather than pretending otherwise.
- **README examples are synthetic.** Output is generated from throwaway repos, never from the user's
  work repositories, whose branch names are internal.
- **PyPI publishing via Trusted Publishing** (GitHub Actions on a version tag), not a stored API token.
