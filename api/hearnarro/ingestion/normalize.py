"""Stage 5 normalization for speech, with a char_map back to the source (subset of ING-6)."""

from __future__ import annotations

import re

SPOKEN_ACRONYMS = {"NASA", "JSON", "SQL", "NATO", "UNESCO", "RAM", "ROM", "GPU", "CPU"}

_PATTERN = re.compile(
    r"(?P<citation>\[\d+(?:\s*[,–-]\s*\d+)*\])"
    r"|(?P<etal>\bet al\.)"
    r"|(?P<percent>\b\d+(?:\.\d+)?%)"
    r"|(?P<url>(?:\bhttps?://|\bwww\.)[^\s/]+(?:/\S*)?)"
    r"|(?P<acronym>\b[A-Z]{2,5}\b)"
)
_URL_TRAILING = ".,;:!?)]}'\"”’"
_DROP_FOLLOWERS = ",.;:!?)"


def _url_host(token: str) -> str:
    rest = re.sub(r"^https?://", "", token)
    host = rest.split("/", 1)[0]
    return host.removeprefix("www.")


def normalize(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, char_map) with len(char_map) == len(normalized_text).

    One left-to-right pass over regex matches (citation, et al., percent, URL, acronym).
    Unmatched characters are copied with identity mapping. A rewritten token at input
    ``[start, start + L)`` with expansion ``E`` (length L') maps output char k to
    ``start + min(L - 1, k * L // L')``: monotone, inside the token, first char -> start
    and, when L' >= L, last char -> start + L - 1. A dropped citation emits nothing; if the
    output then ends in whitespace and the next input char is whitespace, punctuation or the
    end of text, that trailing output space is removed so no double space remains.
    """
    out: list[str] = []
    cmap: list[int] = []

    def emit(s: str, start: int, length: int) -> None:
        n = len(s)
        for k, ch in enumerate(s):
            out.append(ch)
            cmap.append(start + min(length - 1, k * length // n))

    pos = 0
    for m in _PATTERN.finditer(text):
        for i in range(pos, m.start()):
            out.append(text[i])
            cmap.append(i)
        start, end = m.start(), m.end()
        kind = m.lastgroup
        token = m.group()
        suffix_start = end
        if kind == "citation":
            nxt = text[end] if end < len(text) else ""
            if out and out[-1].isspace() and (not nxt or nxt.isspace() or nxt in _DROP_FOLLOWERS):
                out.pop()
                cmap.pop()
        elif kind == "etal":
            emit("et al", start, len(token))
        elif kind == "percent":
            emit(token[:-1] + " percent", start, len(token))
        elif kind == "url":
            trimmed = token.rstrip(_URL_TRAILING)
            suffix_start = start + len(trimmed)
            host = _url_host(trimmed) or trimmed
            emit(host, start, len(trimmed))
        elif kind == "acronym":
            if token in SPOKEN_ACRONYMS:
                emit(token, start, len(token))
            else:
                emit(" ".join(token), start, len(token))
        for i in range(suffix_start, end):
            out.append(text[i])
            cmap.append(i)
        pos = end
    for i in range(pos, len(text)):
        out.append(text[i])
        cmap.append(i)
    return "".join(out), cmap
