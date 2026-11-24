import os
from pathlib import Path
import subprocess
import sys

import pytest

import git_nearest


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX pseudoterminal")
def test_quit_leaves_final_interactive_view_as_cli_output(forked):
    import fcntl
    import pty
    import select
    import struct
    import termios
    import time

    head = forked.git("rev-parse", "HEAD")
    parent = forked.git("rev-parse", "HEAD^")
    pattern = "^refs/remotes/origin/main$"
    command = [sys.executable, "-m", "git_nearest", "--color", "never"]
    env = {**os.environ, "TERM": "xterm", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(Path(git_nearest.__file__).resolve().parents[1])}
    master, slave = pty.openpty()
    process = None
    output = bytearray()
    offset = 0

    def read_through(text):
        nonlocal offset
        needle = text.encode("utf-8")
        deadline = time.monotonic() + 10
        position = output.find(needle, offset)
        while position == -1:
            remaining = deadline - time.monotonic()
            assert remaining > 0 and select.select([master], [], [], remaining)[0], output.decode(
                "utf-8", errors="replace"
            )
            chunk = os.read(master, 65536)
            assert chunk
            output.extend(chunk)
            position = output.find(needle, offset)
        offset = position + len(needle)

    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 100, 0, 0))
        original_terminal = termios.tcgetattr(slave)
        process = subprocess.Popen(
            [*command, "-i"], stdin=slave, stdout=slave, stderr=slave,
            env=env,
        )
        read_through("Center HEAD")
        os.write(master, b"f")
        read_through("Ref regex")
        os.write(master, pattern.encode() + b"\r")
        read_through("Filter " + pattern)
        os.write(master, b"\x1b[B ")
        read_through(parent[:8])
        os.write(master, b"i")
        read_through("Commit " + head)
        os.write(master, b"g")
        read_through("Jump to ref or commit")
        os.write(master, b"origin/feat\r")
        read_through("Center origin/feat")
        os.write(master, b"\x7f")
        read_through("Commit " + head)

        os.write(master, b"q")
        read_through("\x1b[?1049l")
        expected = subprocess.check_output(
            [*command, "--match", pattern, "--expand", head, "--details", head],
            env=env,
        ).replace(b"\n", b"\r\n")
        read_through(expected.decode("utf-8"))
        assert process.wait(timeout=10) == 0
        assert bytes(output).split(b"\x1b[?1049l", 1)[1] == expected
        assert termios.tcgetattr(slave) == original_terminal
        assert forked.git("rev-parse", "HEAD") == head
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)
