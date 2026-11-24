"""A terminal viewer for editing and exploring a nearest-branch graph."""
import codecs
from collections import namedtuple
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
    b"A": "up", b"B": "down", b"C": "right", b"D": "left",
    b"H": "home", b"1~": "home", b"7~": "home",
}
_WIN_KEYS = {"H": "up", "P": "down", "M": "right", "K": "left", "G": "home"}
_DIRECTIONS = {"up": "child", "k": "child", "down": "parent", "j": "parent"}
_REVERSE = {"child": "parent", "parent": "child"}
_SIDES = {"left": -1, "h": -1, "right": 1, "l": 1}
_ENTER = ("\r", "\n")
_BACK = ("\x7f", "\b")
_PROMPTS = {
    "g": "Jump to ref or commit  ",
    "f": "Ref regex (empty clears)  ",
    "n": "Nearby ref limit  ",
}
_IDLE = object()
_Choice = namedtuple("_Choice", "direction options index")


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


def _commit_row(view, oid):
    return next((i for i, row in enumerate(view.rows) if row.oid == oid and row.kind == "commit"), None)


def _size():
    return shutil.get_terminal_size(fallback=(80, 24))


def _wait_for_key(read_key, size, pending):
    while True:
        key = read_key()
        if key is not _IDLE:
            return key
        if pending or _size() != size:
            return _IDLE


def _draw(view, choice, top, message, size, prompt=None):
    columns, height = size
    state = view.state
    label = view.center[:8] if state.rev == view.center else state.rev
    summary = "Center %s   Radius %d   Refs %d   Filter %s" % (
        label, state.radius, state.limit, state.pattern or "default")
    footer = [message or summary, "q Quit   ↑↓ Walk   [ ] Radius   i Details",
              "g Jump   f Filter   n Limit   Backspace Back   Home HEAD"]
    center_row = _commit_row(view, view.center)
    selected_row = None
    if choice is not None:
        selected = choice.options[choice.index]
        selected_row = _commit_row(view, selected)
        arrow = "↑" if choice.direction == "child" else "↓"
        footer.insert(0, "%s %d/%d  %s   ←→ Choose   %s/Enter Go   Esc Cancel" % (
            choice.direction.capitalize(), choice.index + 1, len(choice.options), selected[:8], arrow))
    if prompt is not None:
        label, value = prompt
        if len(label) > columns // 2:
            label = label[:max(0, columns // 2 - 2)] + "  "
        available = max(1, columns - len(label) - 2)
        footer = [label + value[-available:] + "_", "Enter Apply   Esc Cancel   Ctrl+U Clear"]
    footer = footer[:max(0, height - 1)]
    visible = max(1, height - len(footer))
    focus = selected_row if selected_row is not None else center_row
    cursor = 0 if focus is None else focus
    start = cursor
    end = cursor
    if selected_row is not None and center_row is not None and abs(center_row - cursor) < visible:
        start = min(start, center_row)
        end = max(end, center_row)
    if state.details == view.center and cursor == center_row:
        # Keep the center commit and its following detail rows visible together.
        while end + 1 < min(cursor + visible, len(view.rows)) and view.rows[end + 1].kind == "text":
            end += 1
    top = max(0, min(start, top), end - visible + 1)
    top = min(top, max(0, len(view.rows) - visible))
    lines = [("› " if i == focus else "  ") + row.text
             for i, row in enumerate(view.rows[top:top + visible], start=top)]
    lines.extend([""] * (visible - len(lines)))
    lines.extend(footer)
    _terminal_write(_ESC + "[H" + _ESC + "[J" + "\n".join(_fit(line, max(0, columns - 1)) for line in lines))
    return top


def _center(view, rev):
    state = view.state
    details = rev if state.details == view.center else None
    return replace(state, rev=rev, details=details)


def _edit(key, view, value):
    state = view.state
    if key == "g":
        return _center(view, value.strip()) if value.strip() else state
    if key == "f":
        return replace(state, pattern=value or None)
    if key == "n":
        try:
            limit = int(value)
        except ValueError:
            limit = 0
        if limit < 1:
            raise GitError("Enter a positive ref limit.")
        return replace(state, limit=limit)
    if key == "[":
        return replace(state, radius=max(0, state.radius - 1))
    if key == "]":
        return replace(state, radius=state.radius + 1)
    if key == "i":
        return replace(state, details=None if state.details == view.center else view.center)
    return state


def _browse(view, reload, refresh, read_key):
    top = 0
    history = []
    traversed = {}
    choice = None
    prompt = None
    value = ""
    message = ""
    last_size = None
    dirty = True
    refresh_failed = False
    try:
        while True:
            if refresh is not None and view.pending and not refresh_failed:
                try:
                    updated_view = refresh(view)
                except GitError as error:
                    message = " ".join(str(error).splitlines())
                    dirty = refresh_failed = True
                else:
                    dirty = dirty or updated_view is not view
                    view = updated_view
            size = _size()
            if dirty or size != last_size:
                field = (_PROMPTS[prompt], value) if prompt is not None else None
                top = _draw(view, choice, top, message, size, field)
                last_size = size
                dirty = False
            key = _wait_for_key(read_key, size, refresh is not None and view.pending and not refresh_failed)
            if key is _IDLE:
                continue
            dirty = True
            message = ""
            if key in (None, "\x04") or (key == "q" and prompt is None):
                return view
            if prompt is not None:
                if key == _ESC:
                    prompt = None
                    continue
                if key not in _ENTER:
                    if key in _BACK:
                        value = value[:-1]
                    elif key == "\x15":
                        value = ""
                    elif len(key) == 1 and key.isprintable():
                        value += key
                    continue
                key, prompt = prompt, None
            elif key in _PROMPTS:
                prompt, value, choice = key, "", None
                continue

            direction = _DIRECTIONS.get(key)
            target = None
            if key == _ESC:
                choice = None
                continue
            if choice is not None:
                if key in _SIDES:
                    choice = choice._replace(index=(choice.index + _SIDES[key]) % len(choice.options))
                    continue
                if key in _ENTER or direction == choice.direction:
                    direction = choice.direction
                    target = choice.options[choice.index]
                elif direction:
                    continue
            elif direction:
                neighbors = view.children if direction == "child" else view.parents
                if not neighbors:
                    message = "No %s from this commit." % direction
                    continue
                if len(neighbors) > 1:
                    previous = traversed.get((view.center, direction))
                    index = neighbors.index(previous) if previous in neighbors else 0
                    choice = _Choice(direction, neighbors, index)
                    continue
                target = neighbors[0]

            try:
                if target:
                    updated = _center(view, target)
                elif key == "home":
                    updated = _center(view, "HEAD")
                elif key in _BACK and history:
                    updated = history[-1]
                else:
                    updated = _edit(key, view, value)
                if updated == view.state:
                    continue
                next_view = reload(updated)
            except GitError as error:
                message = " ".join(str(error).splitlines())
                continue
            if key in _BACK:
                history.pop()
                choice = None
            elif target or key in ("g", "home"):
                history.append(view.state)
                choice = None
                if target:
                    traversed[view.center, direction] = target
                    traversed[target, _REVERSE[direction]] = view.center
            view = next_view
            refresh_failed = False
    except KeyboardInterrupt:
        return view


def run(view, reload, refresh=None):
    """Return the last valid view, restoring the normal screen before the caller prints it."""
    with _keyboard() as read_key:
        try:
            _terminal_write(_ENTER_SCREEN)
            return _browse(view, reload, refresh, read_key)
        finally:
            _terminal_write(_LEAVE_SCREEN)
