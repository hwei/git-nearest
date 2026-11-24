# Architecture

## Module map

```
src/git_nearest/
  cli.py      parse options into a view state and build a view, using read-only git operations
  refs.py     select branches and rank distinct tips by ahead/behind from the view center
  graph.py    build the compact graph, expand selected folds, and format selectable rows
  tui.py      edit view options with keyboard navigation and restore the terminal on exit
  status.py   git status --porcelain=v1 -> counts -> "[clean]" / "[2 staged, ...]"
  gitutil.py  git() subprocess wrapper, GitError
  color.py    Painter + ANSI codes
tests/        conftest.py builds throwaway repos per test
scripts/
  demo.py     builds the synthetic repo behind the README example and renders docs/img/graph.svg
```

The console script `git-nearest` points at `git_nearest.cli:main`. git runs any `git-<name>` on
`PATH` as `git <name>`.

## Ranking (`refs.py`)

The center is HEAD or the commit that `-b REV` resolves to. Without a pattern, consider
remote-tracking branches. An explicit regular expression can select from local and remote-tracking
branches by full ref name. Skip symbolic refs and the ref that names the center. Sort by the number
of commits exclusive to the center, then by the number exclusive to the tip. Refs on the same commit
share one place in the limit and all their matching names appear in the graph.

Git 2.41 or newer batches counts with `for-each-ref`. With a filter, it reads the selected names from
stdin. Older Git uses one `rev-list --left-right --count` per distinct selected tip.

## View state (`cli.py`, `tui.py`)

The command line sets the initial center, filter, tip limit, expanded folds and selected commit details.
The interactive mode uses the same options to build each new graph. When it exits the interactive
screen, the command prints the final view once. The cursor and scrolling affect only keyboard
navigation. The status note comes from `git status --porcelain=v1` and belongs to the checked-out HEAD.
`--no-status` skips that check.

## Graph (`graph.py`)

The compact graph shows the view center, ref tips and the merge-bases between them. Other commits are
folded until a view asks to expand them.

1. One `rev-list --topo-order --parents <tips> ^<octopus merge-base>` loads the history above the common
   base. Parents outside that set are dropped.
2. `mask[c]` = bitmask of tips that can reach commit `c`.
3. A commit is a node if it is a tip or has no child with the same mask (that is a merge-base).
4. Project each node's parent edges through hidden commits to the nearest visible ancestors.
5. A fold counts the commits reachable from its anchor that are hidden above the next visible ancestors.
   Expanding the fold adds those commits to the visible graph and draws their parent edges.
6. Emit the newest ready node by committer date. Children always precede parents, so with clock skew a
   row can be older than the one below it. Assign lanes in jj/git-log style, joining and splitting
   with `├─╯` and `├─╮`.

## Output conventions

The view center is `@`, a distinct checked-out HEAD is `●`, and other nodes are `○`. Branch tips with
the best ranking carry a `nearest` label. Fold counts appear as dimmed `~  (n)` rows. Color is enabled
with `--color always` or `auto` on a TTY without `NO_COLOR`.
