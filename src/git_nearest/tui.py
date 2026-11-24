"""A terminal viewer for editing and exploring a nearest-branch graph."""
import codecs
from contextlib import contextmanager
from dataclasses import replace
import os
import re
import select
import shutil
import sys
import time
import unicodedata

from .gitutil import GitError


_ESC = "\x1b"
_ENTER_SCREEN = _ESC + "[?1049h" + _ESC + "[?25l"
_LEAVE_SCREEN = _ESC + "[0m" + _ESC + "[?25h" + _ESC + "[?1049l"
_SGR = re.compile(r"\x1b\[[0-9;]*m")
_ARROWS = {
    b"A": "up", b"B": "down", b"H": "home",
    b"1~": "home", b"5~": "pageup", b"6~": "pagedown", b"7~": "home",
}
_WIN_KEYS = {"H": "up", "P": "down", "G": "home", "I": "pageup", "Q": "pagedown"}
_IDLE = object()


def _terminal_write(text):
    sys.stdout.write(text)
    sys.stdout.flush()


class _PosixKeys:
    def __init__(self, fd):
        self.fd = fd
        self.pending = b""
        self.decoder = codecs.getincrementaldecoder(sys.stdin.encoding or "utf-8")(errors="replace")

    def _byte(self, timeout):
        if self.pending:
            byte, self.pending = self.pending, b""
            return byte
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        return os.read(self.fd, 1)

    def _escape(self):
        # Wait briefly for the rest of a cursor key, leaving a standalone Escape usable.
        first = self._byte(0.04)
        if first not in (b"[", b"O"):
            self.pending = first or b""
            return _ESC
        sequence = b""
        while len(sequence) < 16:
            byte = self._byte(0.04)
            if not byte:
                break
            sequence += byte
            if b"@" <= byte <= b"~":
                return _ARROWS.get(sequence, "unknown")
        return "unknown"

    def read(self):
        while True:
            byte = self._byte(0.15)
            if byte is None:
                return _IDLE
            if not byte:
                return None
            if byte == b"\x1b":
                return self._escape()
            decoded = self.decoder.decode(byte)
            if decoded:
                return decoded


def _windows_key():
    import msvcrt

    if not msvcrt.kbhit():
        time.sleep(0.15)
        return _IDLE
    key = msvcrt.getwch()
    if key in ("\x00", "\xe0"):
        return _WIN_KEYS.get(msvcrt.getwch(), "unknown")
    if "\ud800" <= key <= "\udbff":
        key += msvcrt.getwch()
        return key.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return key


@contextmanager
def _keyboard():
    if os.name == "nt":
        yield _windows_key
        return

    import termios
    import tty

    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        yield _PosixKeys(fd).read
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def _fit(text, cells):
    """Fit a colored graph row on one physical terminal line."""
    parts = []
    styled = False
    offset = 0
    while offset < len(text):
        style = _SGR.match(text, offset)
        if style:
            parts.append(style.group())
            offset = style.end()
            styled = True
            continue
        char = text[offset]
        offset += 1
        category = unicodedata.category(char)
        if category in ("Cc", "Cs"):
            continue
        if category in ("Cf", "Mn", "Me"):
            width = 0
        else:
            width = 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
        if width > cells:
            break
        parts.append(char)
        cells -= width
    if styled:
        parts.append(_ESC + "[0m")
    return "".join(parts)


def _selectable(view):
    return [i for i, row in enumerate(view.rows) if row.kind in ("commit", "fold")]


def _focus(view, selection):
    indices = _selectable(view)
    for kind, oid in (selection, ("commit", selection[1]), ("fold", selection[1]), ("commit", view.center)):
        for index in indices:
            row = view.rows[index]
            if row.kind == kind and row.oid == oid:
                return index
    return indices[0]


def _move(view, cursor, key, height):
    indices = _selectable(view)
    index = indices.index(cursor)
    if key in ("up", "k"):
        return indices[max(index - 1, 0)]
    if key in ("down", "j"):
        return indices[min(index + 1, len(indices) - 1)]
    if key == "pageup":
        return next((i for i in reversed(indices) if i <= cursor - height), indices[0])
    return next((i for i in indices if i >= cursor + height), indices[-1])


def _size():
    return shutil.get_terminal_size(fallback=(80, 24))


def _wait_for_key(read_key, size):
    while True:
        key = read_key()
        if key is not _IDLE:
            return key
        if _size() != size:
            return "resize"


def _draw(view, cursor, top, message, size, prompt=None):
    columns, height = size
    state = view.state
    summary = "Center %s   Refs %d   Filter %s" % (state.rev, state.limit, state.pattern or "default")
    footer = [message or summary, "q Quit   ↑↓ Move   Enter Center   Space Fold   i Details",
              "g Jump   f Filter   n Limit   Backspace Back   Home HEAD"]
    if prompt is not None:
        label, value = prompt
        if len(label) > columns // 2:
            label = label[:max(0, columns // 2 - 2)] + "  "
        available = max(1, columns - len(label) - 2)
        footer = [label + value[-available:] + "_", "Enter Apply   Esc Cancel   Ctrl+U Clear"]
    footer = footer[:max(0, height - 1)]
    visible = max(1, height - len(footer))
    end = cursor
    if view.rows[cursor].oid == state.details:
        # Keep the selected commit and its following detail rows visible together.
        while end + 1 < min(cursor + visible, len(view.rows)) and view.rows[end + 1].kind == "text":
            end += 1
    top = max(0, min(cursor, top), end - visible + 1)
    top = min(top, max(0, len(view.rows) - visible))
    lines = [("› " if i == cursor else "  ") + row.text
             for i, row in enumerate(view.rows[top:top + visible], start=top)]
    lines.extend([""] * (visible - len(lines)))
    lines.extend(footer)
    _terminal_write(_ESC + "[H" + _ESC + "[J" + "\n".join(_fit(line, max(0, columns - 1)) for line in lines))
    return top, visible


def _prompt(view, cursor, top, label, read_key):
    value = ""
    while True:
        size = _size()
        top, _ = _draw(view, cursor, top, "", size, (label, value))
        key = _wait_for_key(read_key, size)
        if key in (None, _ESC, "\x04"):
            return None
        if key in ("\r", "\n"):
            return value
        if key in ("\x7f", "\b"):
            value = value[:-1]
        elif key == "\x15":
            value = ""
        elif len(key) == 1 and key.isprintable():
            value += key


def _center(state, rev):
    return replace(state, rev=rev, expanded=(), details=None)


def _edit(key, view, selection, history, read_prompt):
    state = view.state
    kind, oid = selection
    if key in ("\r", "\n") and kind == "commit" and oid != view.center:
        return _center(state, oid)
    if key == "g":
        rev = read_prompt("Jump to ref or commit  ")
        if rev and rev.strip():
            return _center(state, rev.strip())
    if key == "home":
        return _center(state, "HEAD")
    if key in ("\x7f", "\b") and history:
        return history[-1][0]
    if key == "f":
        pattern = read_prompt("Ref regex (empty clears)  ")
        if pattern is not None:
            return replace(state, pattern=pattern or None)
    if key == "n":
        limit = read_prompt("Nearby ref limit  ")
        if limit is not None:
            try:
                limit = int(limit)
            except ValueError:
                limit = 0
            if limit < 1:
                raise GitError("Enter a positive ref limit.")
            return replace(state, limit=limit)
    if key == " ":
        if oid in state.expanded:
            return replace(state, expanded=tuple(anchor for anchor in state.expanded if anchor != oid))
        if kind == "fold":
            return replace(state, expanded=(*state.expanded, oid))
    if key == "i" and kind == "commit":
        return replace(state, details=None if state.details == oid else oid)
    return state


def _browse(view, reload, read_key):
    cursor = _focus(view, ("commit", view.center))
    top = 0
    history = []
    message = ""
    try:
        while True:
            size = _size()
            top, height = _draw(view, cursor, top, message, size)
            key = _wait_for_key(read_key, size)
            if key == "resize":
                continue
            message = ""
            if key in ("q", None, "\x04"):
                return view
            if key in ("up", "down", "j", "k", "pageup", "pagedown"):
                cursor = _move(view, cursor, key, height)
                continue
            if key == "home" and view.state.rev == "HEAD":
                cursor = _focus(view, ("commit", view.center))
                continue
            row = view.rows[cursor]
            selection = row.kind, row.oid
            try:
                updated = _edit(key, view, selection, history,
                                lambda label: _prompt(view, cursor, top, label, read_key))
                if updated == view.state:
                    continue
                next_view = reload(updated)
            except GitError as error:
                message = " ".join(str(error).splitlines())
                continue
            if key in ("\x7f", "\b"):
                _, selection = history.pop()
            elif key in ("\r", "\n", "g", "home"):
                history.append((view.state, selection))
                selection = "commit", next_view.center
            view = next_view
            cursor = _focus(view, selection)
    except KeyboardInterrupt:
        return view


def run(view, reload):
    """Return the last valid view, restoring the normal screen before the caller prints it."""
    with _keyboard() as read_key:
        try:
            _terminal_write(_ENTER_SCREEN)
            return _browse(view, reload, read_key)
        finally:
            _terminal_write(_LEAVE_SCREEN)
