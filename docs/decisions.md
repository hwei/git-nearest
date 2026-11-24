# Decisions

Settled. Do not reopen without the user asking. Add new entries at the bottom: what, and why.

- **Name `git-nearest`.** Works as `git nearest` via the `git-<name>` convention. Was free on PyPI and
  GitHub when checked; re-check right before publishing.
- **Pure standard library, Python >= 3.8.** Zero install friction for a small git helper.
- **MIT license.** Author `hwei <814065+hwei@users.noreply.github.com>` in `pyproject.toml`, `LICENSE`
  and commits. No other email anywhere in the repo.
- **Output glyphs.** The view center is `@`, fold counts are `(n)`, and folded rows use `~`. Matches `jj log` closely
  enough to be familiar.
- **Ranking is a heuristic** (fewest ahead, then fewest behind). git has no notion of a parent branch;
  the README says so rather than pretending otherwise.
- **README examples are synthetic and generated.** `scripts/demo.py` builds a throwaway repo with fixed
  commit dates and prints the output. Never use output from the user's work repositories, whose branch
  names are internal.
- **README examples are SVG images, with the text in a `<details>` below.** GitHub strips ANSI and
  inline styles, so color needs an image. `demo.py` writes the SVGs itself (stdlib, no rich, no
  `freeze`): every character sits at a fixed cell `x` so alignment does not depend on the font,
  ligatures are off, and box-drawing glyphs and `○` are drawn as paths, since fonts draw them with
  gaps (rich's export did, and turned `->` into a ligature). Dark terminal background, one image for
  both GitHub themes. Image links are absolute `raw.githubusercontent.com` URLs because PyPI renders
  the README too and cannot resolve relative paths.
- **PyPI publishing via Trusted Publishing** (GitHub Actions on a version tag), not a stored API token.
- **Fold counts `(n)` are dim, not colored.** They are secondary information; yellow competed with the
  branch names. Yellow stays for the working tree note.
- **`-b/--branch REV` picks the base to measure from** (default HEAD). Any branch or commit works. The
  working tree status describes HEAD. The graph labels the center with the selected revision and
  excludes the selected branch itself as a candidate.
- **Graph rows are ordered newest committer date first, subject to children-before-parents.** Was
  alphabetical by ref with HEAD's line leftmost; that looked arbitrary against the timeline. Cost: HEAD's
  line is no longer guaranteed leftmost or contiguous, and clock skew can break strict time order.
- **Actions are pinned and updated by Dependabot** (`.github/dependabot.yml`, monthly, github-actions only).
  `astral-sh/setup-uv` has no floating major tag, so it is pinned to an exact version. There is no pip
  ecosystem entry: the package has no runtime dependencies.
- **The graph is the default output.** Its fold counts and nearest marker are enough to scan branch
  relationships at a glance. Ahead and behind counts drive ranking internally.
- **Regex filters match full branch refs before selecting the nearest distinct tips.** Full ref names
  distinguish local branches from remote-tracking branches. Branch names that point to the same tip
  share one slot to keep aliases from crowding out other commits.
- **Interactive mode edits the same view options as command mode.** Moving the view center is a read-only
  operation. The final view goes to regular terminal output so it stays beside the shell command in
  scrollback.
