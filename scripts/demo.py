"""Build a synthetic demo repository and print git-nearest's output, for the README examples.

    uv run python scripts/demo.py

Commit dates are fixed, so hashes (and the output) are the same on every run.
"""
import os
import subprocess
import sys
import tempfile

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
        [sys.executable, "-m", "git_nearest", "--color", "never", *args],
        cwd=path, env={**os.environ, **ENV, "PYTHONPATH": os.path.join(ROOT, "src"), "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return p.stdout.rstrip("\n")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        build(tmp)
        table, graph = run(tmp), run(tmp, "-g")
    sys.stdout.reconfigure(encoding="utf-8")
    print("$ git nearest\n" + table + "\n\n$ git nearest -g\n" + graph)


if __name__ == "__main__":
    main()
