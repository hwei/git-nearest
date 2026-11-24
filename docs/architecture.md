# Architecture

## Module map

```
src/git_nearest/
  cli.py         parse options, build the compact view and coordinate radius sessions
  refs.py        select branch labels and rank compact tips by ahead/behind from the view center
  graph.py       build the compact graph and render the radius graph with shared lane drawing
  navigation.py  index local commit edges and search neighborhoods and branch routes
  view.py        shared options, view state and cached radius sessions
  tui.py         walk neighboring commits, edit view options, and restore the terminal on exit
  status.py      git status --porcelain=v1 -> counts -> "[clean]" / "[2 staged, ...]"
  gitutil.py     git() subprocess wrapper, GitError
  color.py       Painter + ANSI codes
tests/           conftest.py builds throwaway repos per test
scripts/
  demo.py        builds the synthetic repo and renders the graph examples under docs/img/
```

The console script `git-nearest` points at `git_nearest.cli:main`. git runs any `git-<name>` on
`PATH` as `git <name>`.

## Branch selection and compact ranking (`refs.py`)

The center is HEAD or the commit that `-b REV` resolves to. Without a pattern, consider
remote-tracking branches. An explicit regular expression can select from local and remote-tracking
branches by full ref name. Skip symbolic refs and the ref that names the center. Refs on the same
commit share one place in the limit and all their matching names appear in the graph.

The compact graph sorts by the number of commits exclusive to the center, then by the number exclusive
to the tip. Git 2.41 or newer batches counts with `for-each-ref`. With a filter, it reads the selected
names from stdin. Older Git uses one `rev-list --left-right --count` per distinct selected tip.

## View state (`cli.py`, `view.py`, `tui.py`)

The command line sets the initial center, filter, tip limit, radius or expanded folds, and selected
commit details. Interactive mode sets a default radius and edits the same options. Its branch choice
is temporary until the user confirms an edge and moves the center. The command prints the last view
on the regular terminal screen after exiting interactive mode. The status note comes from
`git status --porcelain=v1` and belongs to the checked-out HEAD. `--no-status` skips that check.

## Compact graph (`graph.py`)

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

## Radius graph (`navigation.py`, `view.py`, `graph.py`)

Build an adjacency index once with `rev-list --parents` over branch tips, HEAD and the initial center.
Interactive jumps can add ancestry for an unreferenced commit. The index stores parent and child
links. Breadth-first distances select the commits within the radius regardless of the branch filter.
Draw the original parent edges among those commits and add continuations where edges cross the
boundary.

Rank selected, reachable branch tips by shortest path length from the center. A waypoint for a tip
beyond the radius is drawn on the boundary along a shortest route to the tip. Interactive mode
renders the local map before the background waypoint search completes, then waits for the last route
search before printing. It caches recent maps, routes, and commit details for navigation.

## Output conventions

The view center is `@`, a distinct checked-out HEAD is `●`, and other nodes are `○`. The best-ranked
tips carry a `nearest` label. Compact folds use dimmed `~  (n)` rows. The radius graph uses `…` for
boundary continuations and shows branch distances on those rows. Color is enabled with
`--color always` or `auto` on a TTY without `NO_COLOR`.
