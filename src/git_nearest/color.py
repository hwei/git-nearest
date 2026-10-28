"""ANSI styling that can be switched off."""

DIM = "2"
GREEN = "32"
GREEN_BOLD = "1;32"
RED = "31"
YELLOW = "33"
CYAN = "36"


class Painter:
    def __init__(self, enabled):
        self.enabled = enabled

    def __call__(self, code, text):
        if not self.enabled or not text:
            return text
        return "\033[%sm%s\033[0m" % (code, text)
