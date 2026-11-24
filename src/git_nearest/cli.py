import argparse
from collections import Counter
from dataclasses import dataclass, replace
import os
import re
import sys
from typing import Optional, Tuple

from . import __version__, color, graph, refs, status, tui
from .color import Painter
from .gitutil import GitError, git


@dataclass(frozen=True)
class Options:
    limit: int = 5
    rev: str = "HEAD"
    pattern: Optional[str] = None
    expanded: Tuple[str, ...] = ()
    details: Optional[str] = None


@dataclass(frozen=True)
class View:
    state: Options
    center: str
    rows: Tuple[graph.Row, ...]


def _parser():
    parser = argparse.ArgumentParser(
        prog="git nearest",
        description="Draw a compact map of the branches closest to a Git commit.",
    )
    parser.add_argument("limit", nargs="?", type=int, default=5,
                        help="how many distinct branch tips to show (default: 5)")
    parser.add_argument("-b", "--branch", metavar="REV", default="HEAD",
                        help="center the map on this branch or commit (default: HEAD)")
    parser.add_argument("--match", metavar="REGEX",
                        help="match full local and remote branch ref names; without this, show remote branches")
    parser.add_argument("--expand", metavar="REV", action="append", default=[],
                        help="unfold the history below this commit in the map (repeatable)")
    parser.add_argument("--details", metavar="REV", help="show this commit's details")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="explore the map interactively; leave the final map in the terminal")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--no-color", dest="color", action="store_const", const="never",
                        help="same as --color=never")
    parser.add_argument("--no-status", action="store_true",
                        help="don't check the working tree (faster on huge repos)")
    parser.add_argument("--version", action="version", version="git-nearest " + __version__)
    return parser


def _resolve(rev):
    args = ("rev-parse", "--verify", "--end-of-options", rev + "^{commit}")
    if rev == "HEAD":
        return git(*args)
    oid = git(*args, check=False)
    if oid:
        return oid
    raise GitError("not a valid branch or commit: " + _one_line(rev))


def _one_line(text):
    return "".join(c if c.isprintable() else " " for c in text)


def _head_label():
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False)
    return "HEAD -> " + branch if branch else "HEAD (detached)"


def _details(oid):
    subject, author, date, parents = git(
        "show", "-s", "--format=%s%x00%an%x00%aI%x00%P", oid, strip=False
    ).rstrip("\n").split("\0")
    return [
        "Commit " + oid,
        "  " + _one_line(subject),
        "  Author " + _one_line(author),
        "  Date " + date,
        "  Parents " + (parents or "(root)"),
    ]


def _load(state, paint, check_tree):
    try:
        pattern = re.compile(state.pattern) if state.pattern is not None else None
    except re.error as exc:
        raise GitError("invalid branch regex: " + _one_line(str(exc))) from exc

    center = _resolve(state.rev)
    actual_head = center if state.rev == "HEAD" else git(
        "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}", check=False
    )
    skip = git("rev-parse", "--verify", "--symbolic-full-name", "--end-of-options", state.rev, check=False)
    ranked = refs.rank(state.limit, center, skip, pattern=pattern)

    names = {}
    nearest = set()
    labels = Counter(row.ref for row in ranked)
    for row in ranked:
        name = row.full_ref if labels[row.ref] > 1 else row.ref
        names.setdefault(row.oid, []).append(name)
        if (row.ahead, row.behind) == (ranked[0].ahead, ranked[0].behind):
            nearest.add(row.oid)

    expanded = tuple(dict.fromkeys(_resolve(rev) for rev in state.expanded))
    detail_oid = _resolve(state.details) if state.details is not None else None
    state = replace(state, expanded=expanded, details=detail_oid)
    details = (detail_oid, _details(detail_oid)) if detail_oid else None
    if state.rev == "HEAD":
        label = _head_label()
    else:
        label = _one_line(state.rev) + (" [HEAD]" if center == actual_head else "")
    note = status.describe(status.read(), paint) if state.rev == "HEAD" and check_tree else None

    rows = list(graph.render_map(
        names, paint, center, label, note, actual_head=actual_head,
        nearest=nearest, expanded=expanded, details=details,
    ))
    if actual_head and actual_head != center and not any(row.oid == actual_head for row in rows):
        rows.append(graph.Row(paint(color.DIM, _head_label() + " (outside map)"), None, "text"))
    if not ranked:
        message = ("No branches match the filter." if pattern is not None else
                   "No remote branches found (try git fetch or --match '^refs/heads/').")
        rows.append(graph.Row(paint(color.DIM, message), None, "text"))
    return View(state, center, tuple(rows))


def _use_color(mode):
    if mode == "always":
        return True
    return mode == "auto" and sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("limit must be at least 1")
    if args.interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("-i requires an interactive terminal")
    if os.name == "nt" and sys.stdout.isatty():
        os.system("")  # enables ANSI handling in the legacy Windows console
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    paint = Painter(_use_color(args.color))
    state = Options(args.limit, args.branch, args.match, tuple(args.expand), args.details)

    def reload_view(options):
        return _load(options, paint, check_tree=not args.no_status)

    try:
        view = reload_view(state)
        if args.interactive:
            view = tui.run(view, reload_view)
    except GitError as exc:
        print("git-nearest: " + str(exc), file=sys.stderr)
        return 1
    print("\n".join(row.text for row in view.rows))
    return 0
