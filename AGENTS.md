# AGENTS.md

`git nearest` lists the remote branches closest to HEAD (fewest commits ahead, then fewest behind),
as a table or a jj-log-style graph. Pure Python standard library, `requires-python >= 3.8`.

## Commands

```console
uv run pytest            # run the tests
uv run git-nearest -g    # run from source inside any git repo
uv run python scripts/demo.py   # regenerate the README examples
uv build                 # build sdist + wheel into dist/
```

## Read before working

| Doc | Read it when |
|---|---|
| [docs/architecture.md](docs/architecture.md) | changing code: module map, how ranking and the graph work |
| [docs/development.md](docs/development.md) | writing tests or debugging: setup, platform notes, gotchas |
| [docs/decisions.md](docs/decisions.md) | before proposing a rename, new dependency, output change: settled decisions |
| [docs/roadmap.md](docs/roadmap.md) | picking up work: what is done, what is next |
| [docs/maintaining-docs.md](docs/maintaining-docs.md) | **always, before ending a task**: how to keep these docs current |

`HANDOFF.md`, if present, is a local-only note (excluded via `.git/info/exclude`) with machine-specific
context. Read it, never commit it, never copy its contents into tracked files.

## Hard rules

- Anything outward-facing (create or push to the GitHub repo, publish to PyPI, post anywhere) needs
  explicit confirmation from the user first, every time.
- This repo is public. Never put real output, branch names, paths or emails from the user's other
  repositories or employer into tracked files. README examples come from synthetic throwaway repos.
- Commit only as the repo-local identity `hwei <814065+hwei@users.noreply.github.com>`. Check
  `git config user.email` before committing.
- No runtime dependencies. Keep Python 3.8 syntax: no `match`, no `X | Y` or `list[int]` annotations
  evaluated at runtime, no parenthesized context managers (CI runs 3.8).
- Finish every task by applying [docs/maintaining-docs.md](docs/maintaining-docs.md).
