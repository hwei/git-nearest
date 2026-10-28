# Architecture

## Module map

```
src/git_nearest/
  cli.py      argparse, color decision, Windows console setup, wiring
  refs.py     rank(): ahead/behind of a base commit against every ref under refs/remotes, sorted
  table.py    default output: head line + one row per ref
  graph.py    jj-log-style graph (-g)
  status.py   git status --porcelain=v1 -> counts -> "[clean]" / "[2 staged, ...]"
  gitutil.py  git() subprocess wrapper, GitError
  color.py    Painter + ANSI codes
tests/        conftest.py builds throwaway repos per test
scripts/
  demo.py     builds the synthetic repo behind the README examples
```

The console script `git-nearest` points at `git_nearest.cli:main`. git runs any `git-<name>` on
`PATH` as `git <name>`.

## Ranking (`refs.py`)

The base is HEAD, or the commit `-b REV` resolves to (`cli.py` resolves it once and passes the sha down;
the working tree status is only read for HEAD). One `git for-each-ref --format=%(ahead-behind:<base>)` call covers every remote ref (git >= 2.41).
If it returns nothing (older git), fall back to one `rev-list --left-right --count ref...HEAD` per ref.
`*/HEAD` symbolic refs and the ref named by `-b` itself are skipped. Sort key: `(ahead, behind, refname)`. Refs with identical tips all
appear, so ties are visible.

## Table (`table.py`, `status.py`)

First line: `@  HEAD -> <branch>  <status note>` (or `HEAD (detached)`). The status note comes from
`git status --porcelain=v1`; it is red when there are conflicts. `--no-status` skips it because
`git status` is the slow part on big repositories. Then one row per ref: `↑ahead ↓behind  ref  merge-base`.

## Graph (`graph.py`)

Only HEAD, ref tips and the merge-bases between them are drawn; everything else is folded.

1. One `rev-list --topo-order --parents <tips> ^<octopus merge-base>` loads the history above the common
   base. Parents outside that set are dropped.
2. `mask[c]` = bitmask of tips that can reach commit `c`.
3. A commit is a node if it is a tip or has no child with the same mask (that is a merge-base).
4. `allanc` bitmasks give each node its nearest ancestor nodes.
5. Fold count for an edge = `rev-list --count node ^ancestors` minus 1, drawn as a `~  (n)` row.
6. Nodes are emitted in a Kahn order that keeps HEAD's line leftmost; lanes are assigned jj/git-log
   style, with `├─╯` / `├─╮` joining and splitting them.

## Output conventions

HEAD marker `@` (also marks the `-b` base), nodes `○`, folded rows `~  (n)` with the count dimmed (secondary
information), a legend line at the bottom of the graph. Color only
when `--color always`, or `auto` on a TTY without `NO_COLOR`.
