import argparse
import os
import sys

from . import __version__, color, graph, refs, status, table
from .color import Painter
from .gitutil import GitError, git


def _parser():
    p = argparse.ArgumentParser(
        prog="git nearest",
        description="List the remote branches closest to HEAD (fewest commits ahead, then fewest behind).",
    )
    p.add_argument("limit", nargs="?", type=int, default=5, help="how many refs to show (default: 5)")
    p.add_argument("-b", "--branch", metavar="REV", default="HEAD",
                   help="measure from this branch or commit instead of HEAD (skips the working tree check)")
    p.add_argument("-g", "--graph", action="store_true", help="draw how HEAD and those refs relate")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--no-color", dest="color", action="store_const", const="never", help="same as --color=never")
    p.add_argument("--no-status", action="store_true", help="don't check the working tree (faster on huge repos)")
    p.add_argument("--version", action="version", version="git-nearest " + __version__)
    return p


def head_label(rev):
    """How to name the commit we measure from: "HEAD -> main", "HEAD (detached)", or REV as typed."""
    if rev != "HEAD":
        return rev
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False)
    return "HEAD -> " + branch if branch else "HEAD (detached)"


def head_line(label, note, paint):
    """The line above the table: what we measure from and whether the working tree is clean."""
    line = "%s  %s" % (paint(color.GREEN_BOLD, "@"), paint(color.GREEN_BOLD, label))
    return line + "  " + note if note else line


def _use_color(mode):
    if mode == "always":
        return True
    return mode == "auto" and sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.limit < 1:
        sys.exit("git-nearest: limit must be at least 1")
    if os.name == "nt":
        os.system("")  # turns on ANSI escape handling in the legacy Windows console
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        base = git("rev-parse", "--verify", "-q", args.branch + "^{commit}", check=args.branch == "HEAD")
        if not base:
            raise GitError("not a valid branch or commit: " + args.branch)
        skip = git("rev-parse", "--symbolic-full-name", args.branch, check=False)
        rows = refs.rank(args.limit, base, skip)
        if not rows:
            print("git-nearest: no remote branches found (try `git fetch`)", file=sys.stderr)
            return 1
        paint = Painter(_use_color(args.color))
        # the working tree belongs to HEAD, so it says nothing about another branch
        checks_tree = args.branch == "HEAD" and not args.no_status
        note = status.describe(status.read(), paint) if checks_tree else None
        label = head_label(args.branch)
        if args.graph:
            lines = graph.render([r.ref for r in rows], paint, base, label, note)
        else:
            lines = table.render(rows, paint, base, head_line(label, note, paint) if note or args.branch != "HEAD" else None)
    except GitError as e:
        print("git-nearest: " + str(e), file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0
