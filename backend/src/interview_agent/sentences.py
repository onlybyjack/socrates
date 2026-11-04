"""Split a streamed text into speakable sentences."""

import re

# Sentence end: . ? ! … followed by whitespace, or a newline. A '.' between digits is not an end.
_BOUNDARY = re.compile(r"(?<!\d\.)(?<=[.?!…])\s+|\n+")


class SentenceSplitter:
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        parts = _BOUNDARY.split(self._buf)
        self._buf = parts.pop()  # last part is incomplete
        return [p.strip() for p in parts if p.strip()]

    def flush(self) -> list[str]:
        rest, self._buf = self._buf.strip(), ""
        return [rest] if rest else []
