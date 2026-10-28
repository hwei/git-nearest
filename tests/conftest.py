import os
import subprocess

import pytest

ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


class Repo:
    def __init__(self, path):
        self.path = str(path)
        self.count = 0  # unique messages: identical parent/tree/message/second would give identical commits

    def git(self, *args):
        p = subprocess.run(
            ["git", *args], cwd=self.path, env={**os.environ, **ENV},
            capture_output=True, text=True, check=True,
        )
        return p.stdout.strip()

    def commit(self, n=1):
        for _ in range(n):
            self.count += 1
            self.git("commit", "-q", "--allow-empty", "-m", "c%d" % self.count)

    def remote(self, name, rev="HEAD"):
        self.git("update-ref", "refs/remotes/" + name, self.git("rev-parse", rev))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = Repo(tmp_path)
    r.git("init", "-q", "-b", "main")
    monkeypatch.chdir(tmp_path)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    # one fixed second: the graph orders by date, so commits straddling a second would change the layout
    monkeypatch.setenv("GIT_COMMITTER_DATE", "1000000000 +0000")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "1000000000 +0000")
    return r


@pytest.fixture
def forked(repo):
    """main and feat fork from a3; feat is merged into main; work branches off main.

        work:  w1 w2
        main:  a1 a2 a3 m1 m2 M(merge feat) m3 m4
        feat:  a3 f1 f2 f3
    """
    repo.commit(3)
    repo.git("checkout", "-q", "-b", "feat")
    repo.commit(3)
    repo.remote("origin/feat")
    repo.git("checkout", "-q", "main")
    repo.commit(2)
    repo.remote("origin/main")
    repo.git("merge", "-q", "--no-ff", "feat", "-m", "merge feat")
    repo.commit(2)
    repo.git("checkout", "-q", "-b", "work")
    repo.commit(2)
    repo.remote("origin/other", "main~1")
    return repo
