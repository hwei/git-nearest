import argparse
from collections import Counter
from dataclasses import replace
import os
import sys

from . import __version__, color, graph, refs, status, tui
from .color import Painter
from .gitutil import GitError, git
from .view import (
    Options, RadiusSession, View, branches_message, commit_details, compile_pattern,
    head_label, one_line, resolve, symbolic,
)


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
    parser.add_argument("--radius", metavar="N", type=int,
                        help="show commits within N parent/child steps (interactive default: 3)")
    parser.add_argument("--expand", metavar="REV", action="append", default=[],
                        help="unfold the history below this commit in the compact map (repeatable)")
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


def _load(state, paint, check_tree):
    pattern = compile_pattern(state.pattern)
    center = resolve(state.rev)
    actual_head = center if state.rev == "HEAD" else git(
        "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}", check=False
    )
    skip = symbolic(state.rev)
    ranked = refs.rank(state.limit, center, skip, pattern=pattern)

    names = {}
    nearest = set()
    labels = Counter(row.ref for row in ranked)
    for row in ranked:
        name = row.full_ref if labels[row.ref] > 1 else row.ref
        names.setdefault(row.oid, []).append(name)
        if (row.ahead, row.behind) == (ranked[0].ahead, ranked[0].behind):
            nearest.add(row.oid)

    expanded = tuple(dict.fromkeys(resolve(rev) for rev in state.expanded))
    detail_oid = resolve(state.details) if state.details is not None else None
    state = replace(state, expanded=expanded, details=detail_oid)
    details = (detail_oid, commit_details(detail_oid)) if detail_oid else None
    if state.rev == "HEAD":
        label = head_label()
    else:
        label = one_line(state.rev) + (" [HEAD]" if center == actual_head else "")
    note = status.describe(status.read(), paint) if state.rev == "HEAD" and check_tree else None

    rows = list(graph.render_map(
        names, paint, center, label, note, actual_head=actual_head,
        nearest=nearest, expanded=expanded, details=details,
    ))
    if actual_head and actual_head != center and not any(row.oid == actual_head for row in rows):
        rows.append(graph.Row(paint(color.DIM, head_label() + " (outside map)"), None, "text"))
    if not ranked:
        message = branches_message(state.pattern)
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
    radius = 3 if args.interactive and args.radius is None else args.radius
    if radius is not None and radius < 0:
        parser.error("radius must be at least 0")
    if args.expand and radius is not None:
        parser.error("--expand applies only to the compact map")
    if args.interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("-i requires an interactive terminal")
    if os.name == "nt" and sys.stdout.isatty():
        os.system("")  # enables ANSI handling in the legacy Windows console
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    paint = Painter(_use_color(args.color))
    state = Options(args.limit, args.branch, args.match, tuple(args.expand), args.details, radius)
    check_tree = not args.no_status

    try:
        if radius is None:
            view = _load(state, paint, check_tree)
        else:
            session = RadiusSession(state, paint, check_tree)
            try:
                if args.interactive:
                    view = tui.run(session.load(state), session.load, session.refresh)
                    state = view.state
                view = session.load(state, wait=True)
            finally:
                session.close()
    except GitError as exc:
        print("git-nearest: " + str(exc), file=sys.stderr)
        return 1
    print("\n".join(row.text for row in view.rows))
    return 0
