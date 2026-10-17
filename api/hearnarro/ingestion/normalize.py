"""Stage 5 normalization for speech, with a char_map back to the source (subset of ING-6).

All-caps tokens are left as written: whether "TED" is spoken or "PDF" spelled is decided by
the synthesis backend (``hearnarro.synthesis.acronyms``, SYN-4), which has a pronunciation
lexicon and the document's acronym definitions (``hearnarro.ingestion.acronyms``).
"""

from __future__ import annotations

import re

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
# Lowercase only, so a missing space after a sentence end ("the end.So we") is not a domain.
_TLDS = r"com|org|net|io|ai|co|edu|gov|dev|app|me|us|uk|de|fr|ca|info|biz|tv|ly|so|xyz"
# "https:// host" and "www. host" (a PDF line break) still reach the host.
_SPACE_BEFORE_HOST = r"(?:\s(?=[\w-]+\.\w))?"

_PATTERN = re.compile(
    r"(?P<citation>\[\d+(?:\s*[,–-]\s*\d+)*\])"
    r"|(?P<etal>\bet al\.)"
    r"|(?P<percent>\b\d+(?:\.\d+)?%)"
    rf"|(?P<url>(?:\bhttps?://{_SPACE_BEFORE_HOST}(?:www\.)?|\bwww\.{_SPACE_BEFORE_HOST})"
    r"[^\s/]+(?:/\S*)?)"
    rf"|(?P<email>(?<![\w.+-])[A-Za-z0-9._%+-]+@{_LABEL}(?:\.{_LABEL})*\.[A-Za-z]{{2,}}\b)"
    rf"|(?P<domain>(?<![\w@./:-])(?:{_LABEL}\.)+(?:{_TLDS})(?![\w-]|\.\w)(?:/\S*)?)"
)
_URL_PREFIX = re.compile(r"(?:https?://\s?(?:www\.)?|www\.\s?)")
_URL_TRAILING = ".,;:!?)]}'\"”’"
_DROP_FOLLOWERS = ",.;:!?)"
# A path is spoken ("/a/b" -> " slash a slash b") only when it is short and plain.
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_PATH_MAX_SEGMENTS = 3
_PATH_MAX_CHARS = 30
_SPOKEN = {".": " dot ", "/": " slash ", "@": " at "}


def normalize(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, char_map) with len(char_map) == len(normalized_text).

    One left-to-right pass over regex matches (citation, et al., percent, URL, e-mail,
    bare domain).
    Unmatched characters are copied with identity mapping. A rewritten token at input
    ``[start, start + L)`` with expansion ``E`` (length L') maps output char k to
    ``start + min(L - 1, k * L // L')``: monotone, inside the token, first char -> start
    and, when L' >= L, last char -> start + L - 1. A dropped citation emits nothing; if the
    output then ends in whitespace and the next input char is whitespace, punctuation or the
    end of text, that trailing output space is removed so no double space remains.

    Web addresses are spoken as a person reads them (``_emit_address``): the scheme and
    ``www.`` emit nothing, each ``.`` / ``@`` / ``/`` becomes " dot " / " at " / " slash "
    with every output char mapped onto that one source char, letters map to themselves, and
    a path longer than 3 segments or 30 chars (or with non-plain segments) is dropped.
    Trailing sentence punctuation after the address stays as text.
    """
    out: list[str] = []
    cmap: list[int] = []

    def emit(s: str, start: int, length: int) -> None:
        n = len(s)
        for k, ch in enumerate(s):
            out.append(ch)
            cmap.append(start + min(length - 1, k * length // n))

    def emit_char(i: int) -> None:
        for ch in _SPOKEN.get(text[i], text[i]):
            out.append(ch)
            cmap.append(i)

    def emit_address(start: int, end: int, kind: str) -> None:
        """Speak ``text[start:end]`` (a trimmed URL, e-mail or bare domain)."""
        token = text[start:end]
        i = start
        if kind == "url":
            prefix = _URL_PREFIX.match(token)
            i += prefix.end() if prefix else 0
        host_end = i
        while host_end < end and text[host_end] not in "/?#":
            host_end += 1
        for k in range(i, host_end):
            emit_char(k)
        path = text[host_end:end]
        if not path.startswith("/"):
            return
        segments = path.strip("/").split("/")
        if (
            len(segments) > _PATH_MAX_SEGMENTS
            or len(path) > _PATH_MAX_CHARS
            or not all(_PATH_SEGMENT.fullmatch(seg) for seg in segments)
        ):
            return
        for k in range(host_end, host_end + len(path.rstrip("/"))):
            emit_char(k)

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
        elif kind in ("url", "email", "domain"):
            trimmed = token.rstrip(_URL_TRAILING)
            suffix_start = start + len(trimmed)
            emit_address(start, suffix_start, kind)
        for i in range(suffix_start, end):
            out.append(text[i])
            cmap.append(i)
        pos = end
    for i in range(pos, len(text)):
        out.append(text[i])
        cmap.append(i)
    return "".join(out), cmap
