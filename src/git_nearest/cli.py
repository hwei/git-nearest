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
    p.add_argument("-g", "--graph", action="store_true", help="draw how HEAD and those refs relate")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--no-color", dest="color", action="store_const", const="never", help="same as --color=never")
    p.add_argument("--no-status", action="store_true", help="don't check the working tree (faster on huge repos)")
    p.add_argument("--version", action="version", version="git-nearest " + __version__)
    return p


def head_line(note, paint):
    """The line above the table: where HEAD is and whether the working tree is clean."""
    if note is None:
        return None
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False)
    label = "HEAD -> " + branch if branch else "HEAD (detached)"
    return "%s  %s  %s" % (paint(color.GREEN_BOLD, "@"), paint(color.GREEN_BOLD, label), note)


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
        git("rev-parse", "--verify", "-q", "HEAD")
        rows = refs.rank(args.limit)
        if not rows:
            print("git-nearest: no remote branches found (try `git fetch`)", file=sys.stderr)
            return 1
        paint = Painter(_use_color(args.color))
        note = None if args.no_status else status.describe(status.read(), paint)
        if args.graph:
            lines = graph.render([r.ref for r in rows], paint, note)
        else:
            lines = table.render(rows, paint, head_line(note, paint))
    except GitError as e:
        print("git-nearest: " + str(e), file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0
