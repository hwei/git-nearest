"""Build a synthetic demo repository and print git-nearest's output, for the README examples.

    uv run python scripts/demo.py

Prints the plain text and writes the colored version to docs/img/table.svg and docs/img/graph.svg.
Commit dates are fixed, so hashes (and the output) are the same on every run.
"""
import os
import re
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {
    "GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.com",
    "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "demo@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


class Demo:
    def __init__(self, path):
        self.path = path
        self.t = 1700000000

    def git(self, *args):
        env = {**os.environ, **ENV}
        return subprocess.run(
            ["git", *args], cwd=self.path, env=env, capture_output=True, text=True, check=True
        ).stdout.strip()

    def commit(self, *messages):
        for m in messages:
            self.t += 600
            date = "%d +0000" % self.t
            os.environ["GIT_AUTHOR_DATE"] = os.environ["GIT_COMMITTER_DATE"] = date
            self.git("commit", "-q", "--allow-empty", "-m", m)

    def push(self, name, rev="HEAD"):
        self.git("update-ref", "refs/remotes/origin/" + name, self.git("rev-parse", rev))


def build(path):
    d = Demo(path)
    d.git("init", "-q", "-b", "main")
    d.commit("initial import", "add parser", "add tests")
    d.git("checkout", "-q", "-b", "feature/login")
    d.commit("login form", "session cookie", "remember me")
    d.push("feature/login")
    d.git("checkout", "-q", "main")
    d.commit("fix parser edge case", "bump version")
    d.git("checkout", "-q", "-b", "release/1.2")
    d.commit("hotfix: crash on empty input")
    d.push("release/1.2")
    d.git("checkout", "-q", "main")
    d.commit("update changelog")
    d.git("merge", "-q", "--no-ff", "feature/login", "-m", "merge feature/login")
    d.commit("refactor config", "docs: usage")
    d.push("main")
    d.git("checkout", "-q", "-b", "fix-typo")
    d.commit("fix typo in help", "reword error message")
    with open(os.path.join(path, "README"), "w") as f:
        f.write("draft\n")
    d.git("add", "README")
    with open(os.path.join(path, "notes.txt"), "w") as f:
        f.write("todo\n")
    return d


def run(path, *args):
    p = subprocess.run(
        [sys.executable, "-m", "git_nearest", "--color", "always", *args],
        cwd=path, env={**os.environ, **ENV, "PYTHONPATH": os.path.join(ROOT, "src"), "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return p.stdout.rstrip("\n")


# --- SVG rendering of ANSI output ---------------------------------------------------------------
# Every character sits in a fixed cell, so alignment does not depend on the font. Box-drawing glyphs
# and the ○ node are drawn as paths, not text: fonts draw them with gaps or not at all.

SGR = re.compile(r"\033\[([0-9;]*)m")
CELL_W, CELL_H, FONT = 8.4, 20, 14
PAD, BAR = 16, 28
BG, FG = "#161b22", "#c9d1d9"
COLORS = {"31": "#f85149", "32": "#3fb950", "33": "#d29922", "36": "#39c5cf"}
# glyph -> segments from the cell center: u(p), d(own), l(eft), r(ight); ╮ ╯ are rounded corners
BOX = {"│": "ud", "─": "lr", "├": "udr", "┤": "udl", "┴": "lru", "┼": "udlr", "╮": "ld", "╯": "lu"}


def strip(text):
    return SGR.sub("", text)


def cells(line):
    """[(char, style)] for one line, style = (color, bold, dim)."""
    out, style = [], (None, False, False)
    for i, part in enumerate(SGR.split(line)):
        if i % 2:
            c, bold, dim = style
            for code in (part or "0").split(";"):
                if code == "0":
                    c, bold, dim = None, False, False
                elif code == "1":
                    bold = True
                elif code == "2":
                    dim = True
                elif code in COLORS:
                    c = code
            style = (c, bold, dim)
        else:
            out += [(ch, style) for ch in part]
    return out


def attrs(style):
    c, bold, dim = style
    a = ' fill="%s"' % COLORS.get(c, FG)
    if bold:
        a += ' font-weight="bold"'
    if dim:
        a += ' fill-opacity="0.5"'
    return a


def box_path(glyph, x, y):
    cx, cy, r = x + CELL_W / 2, y + CELL_H / 2, CELL_W / 2
    if glyph == "╮":
        return "M%g %gA%g %g 0 0 1 %g %gV%g" % (x, cy, r, r, cx, cy + r, y + CELL_H)
    if glyph == "╯":
        return "M%g %gA%g %g 0 0 0 %g %gV%g" % (x, cy, r, r, cx, cy - r, y)
    ends = {"u": (cx, y), "d": (cx, y + CELL_H), "l": (x, cy), "r": (x + CELL_W, cy)}
    return "".join("M%g %gL%g %g" % (cx, cy, *ends[s]) for s in BOX[glyph])


def svg(command, output):
    lines = [[("$", ("32", False, False)), (" ", None)] + [(ch, (None, True, False)) for ch in command]]
    lines += [cells(line) for line in output.split("\n")]
    cols = max(len(line) for line in lines)
    width, height = 2 * PAD + cols * CELL_W, BAR + PAD + len(lines) * CELL_H + PAD
    body = []
    for row, line in enumerate(lines):
        y = BAR + PAD + row * CELL_H
        baseline = y + CELL_H / 2 + FONT * 0.35
        run, xs, run_style = "", [], None

        def flush():
            if run:
                body.append('<text x="%s" y="%g"%s>%s</text>' % (
                    " ".join("%g" % v for v in xs), baseline, attrs(run_style), escape(run)))

        for col, (ch, style) in enumerate(line):
            x = PAD + col * CELL_W
            if ch == " " or ch in BOX or ch == "○" or style != run_style:
                flush()
                run, xs, run_style = "", [], style
            if ch in BOX:
                body.append('<path d="%s" stroke="%s" stroke-opacity="0.5" fill="none" stroke-width="1.3"/>'
                            % (box_path(ch, x, y), COLORS.get(style[0], FG)))
            elif ch == "○":
                body.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke-width="1.5" stroke="%s"%s/>' % (
                    x + CELL_W / 2, y + CELL_H / 2, CELL_W * 0.36, COLORS.get(style[0], FG),
                    ' stroke-opacity="0.5"' if style[2] else ""))
            elif ch != " ":
                run += ch
                xs.append(x)
        flush()
    dots = "".join('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (PAD + 4 + i * 20, BAR / 2 + 4, c)
                   for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%g" height="%g" viewBox="0 0 %g %g">\n'
        '<style>text{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",'
        'monospace;font-size:%dpx;font-variant-ligatures:none;white-space:pre}</style>\n'
        '<rect width="100%%" height="100%%" rx="8" fill="%s"/>\n%s\n%s\n</svg>\n'
    ) % (width, height, width, height, FONT, BG, dots, "\n".join(body))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        build(tmp)
        table, graph = run(tmp), run(tmp, "-g")
    img = os.path.join(ROOT, "docs", "img")
    os.makedirs(img, exist_ok=True)
    for name, command, output in (("table", "git nearest", table), ("graph", "git nearest -g", graph)):
        with open(os.path.join(img, name + ".svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg(command, output))
    sys.stdout.reconfigure(encoding="utf-8")
    print("$ git nearest\n" + strip(table) + "\n\n$ git nearest -g\n" + strip(graph))


if __name__ == "__main__":
    main()
