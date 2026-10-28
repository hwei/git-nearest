# git-nearest

Which remote branch is my current branch closest to?

```console
$ git nearest
@  HEAD -> work  [clean]
↑3 ↓0  origin/other  82fe5dee
↑7 ↓0  origin/feat   8b947de7
↑8 ↓0  origin/main   d6034859
```

The first line shows where HEAD is and the state of the working tree: `[clean]`, or counts such as
`[2 staged, 3 modified, 1 untracked]` (conflicted files turn it red). That is the thing to check
before moving the branch somewhere else.

`↑` is how many commits HEAD has that the remote branch doesn't, `↓` is how many the remote branch
has that HEAD doesn't, and the last column is the merge-base. The closest branch (fewest `↑`, then
fewest `↓`) comes first. Remote branches with the same tip all show up, so you can see ties
instead of having one picked for you.

## Graph

`git nearest -g` draws how HEAD and those branches relate, in the style of
[`jj log`](https://docs.jj-vcs.dev/): newest on top, and runs of ordinary commits folded into a
`~  (n)` row on the vertical line.

```console
$ git nearest -g
@  e6a7a57e  HEAD -> work  [clean]
~  (2)
○  82fe5dee  origin/other
├─╮
~ │  (1)
○ │  8b947de7  origin/feat
~ │  (2)
│ ○  d6034859  origin/main
│ ~  (1)
├─╯
○  a01d21a0  merge-base
~ (n) = n commits folded between
```

Only HEAD, the branch tips and the merge-bases between them are drawn. `(2)` means two commits sit
between the nodes above and below it.

## Install

Needs Python 3.8+ and git. No other dependencies.

```console
uv tool install git-nearest      # or: pipx install git-nearest
```

The package installs an executable called `git-nearest`; git runs any `git-<name>` on your `PATH` as
`git <name>`.

## Usage

```
git nearest [N] [-g] [--no-status] [--color {auto,always,never}] [--no-color]
```

| | |
|---|---|
| `N` | how many branches to show (default 5) |
| `-g`, `--graph` | draw the graph instead of the table |
| `--no-status` | skip the working tree check (it runs `git status`, which can be slow on huge repositories) |
| `--color` | `auto` (default) colors only on a terminal and respects `NO_COLOR` |

## How it works

git has no notion of a branch's "parent", only of common ancestors, so this is a heuristic, not a
lookup. For every ref under `refs/remotes` it asks git for the ahead/behind counts against HEAD in a
single `for-each-ref --format='%(ahead-behind:HEAD)'` call (git 2.41+; older versions fall back to one
`rev-list` per ref, which is slower on repositories with many branches).

The graph walks the history above the common base once, marks which tips can reach each commit, and
keeps only the commits where those sets change. Those are the merge-bases.

## Limitations

- "Nearest" is by commit count. If you branched from `main` last week and `release/1.0` happens to be
  two commits behind `main`, `release/1.0` is nearer. Look at the graph when it matters.
- Branches that are not in `refs/remotes` are ignored. Run `git fetch` first.
- Folded counts on a node with two parents are the commits unique to that node, shown once.

## Similar tools

- Scripts based on `git show-branch` or on grepping `git log --decorate` for `origin/` (the usual
  Stack Overflow answers) look only at the first decorated ancestor, so they miss ties and give no
  distance.
- [Git Town](https://www.git-town.com/) records a parent for each branch when it creates the branch.
  That is exact but only works for branches it knows about; `git-nearest` infers from history and needs
  no setup.

## Development

```console
uv run pytest
```

## License

MIT
