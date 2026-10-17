"""Expression trees from span geometry (D37, spec §3b; MATH-1, MATH-2).

Stage 1 keeps ``Span`` runs (one font, size and superscript flag each) with bboxes; that is the
finest geometry used here (spec §3a, Q5). ``parse`` turns a ``MathSpan``'s runs into a ``Node``:

- a run smaller than the span's main size is a script: ``sup`` when its superscript flag is set or
  its centre sits above the base row's centre, else ``sub``; Unicode script characters (``²``,
  ``ᵢ``) are scripts too;
- full-size runs whose top lies more than half a size below the current row start a new row; two
  rows are a stacked fraction ``frac`` (the top row's text after its last top-level relation is
  the numerator, so ``x = (−b ± …)`` over ``2a`` keeps ``x =`` outside), a bracketed stack of
  rows with equal cell counts is a ``matrix``;
- ``∑ ∏ ∫ ∮`` take their scripts as limits (``sum``, ``prod``, ``int``); ``lim max min sup inf
  argmin argmax`` take a subscript (``limop``); ``√`` takes the next item (``sqrt``);
- brackets make ``group``; a bracket pair holding one top-level comma is an ``interval`` when its
  brackets are mixed or square, or when ``(…)`` follows ``∈``/``∉`` (the reader speaks it as a
  list under a ``prose`` profile); a letter, a function name or a scripted letter followed by a
  group is ``apply``; paired ``| |`` and ``‖ ‖`` are ``abs`` and ``norm``.

``parse`` returns ``None`` when it cannot structure the span (an unknown character, unbalanced
brackets, a script with no base, three or more rows that are not a matrix); the reader then falls
back to MATH-1's "equation N" plus every symbol by name.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from hearnarro.ingestion.mathspeak import symbols as sy

try:  # spec §3a: m5-p3a adds MathSpan to models.py; until then this identical shape stands in
    from hearnarro.ingestion.models import MathSpan  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - removed once models.py carries MathSpan
    from hearnarro.ingestion.models import Span

    @dataclass
    class MathSpan:  # type: ignore[no-redef]
        start: int
        end: int
        display: bool
        runs: list[Span]
        label: str | None = None


@dataclass
class Node:
    kind: str
    children: list[Node | None] = field(default_factory=list)
    text: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "children": [c.to_json() if c is not None else None for c in self.children],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Node:
        kids = [cls.from_json(c) if c is not None else None for c in data.get("children", [])]
        return cls(data["kind"], kids, data.get("text", ""))


class _Fail(Exception):
    pass


@dataclass
class _Tok:
    kind: str  # num var greek word op open close bar dbar bigop sqrt script prime accent dots
    text: str
    script: str = ""  # "sup" / "sub" for a script token
    inner: list[_Tok] = field(default_factory=list)


LIMOPS = {"lim", "max", "min", "sup", "inf", "argmin", "argmax"}
WORDS = {w for w in sy.FUNCTIONS if w.isascii() and len(w) > 1} | LIMOPS
RELATIONS = set(sy.CONVENTION["relations"]) | {"→", "⇒", "⟹", "⇔", "⟺", "↦"}
OPEN, CLOSE = "([{⟨", ")]}⟩"
BIGOPS = {"∑": "sum", "∏": "prod", "∫": "int", "∮": "int"}
_NUM = re.compile(r"\d+(?:\.\d+)?")
_LABEL_TAIL = re.compile(r"\s*\(\s*(\d+(?:\.\d+)*)\s*\)\s*$")


def _lex(text: str) -> list[_Tok]:
    # Decompose accented letters (x̂ -> x + hat) but not symbols (≠ and ∉ must stay whole).
    text = "".join(
        unicodedata.normalize("NFD", c) if unicodedata.category(c).startswith("L") else c
        for c in text
    )
    out: list[_Tok] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isascii() and ch.isdigit():
            m = _NUM.match(text, i)
            assert m is not None
            out.append(_Tok("num", m.group(0)))
            i = m.end()
        elif ch.isascii() and ch.isalpha():
            j = i
            while j < len(text) and text[j].isascii() and text[j].isalpha():
                j += 1
            run = text[i:j]
            if run in WORDS:
                out.append(_Tok("word", run))
            else:
                out.extend(_Tok("var", c) for c in run)
            i = j
        elif text.startswith("...", i):
            out.append(_Tok("dots", "…"))
            i += 3
        elif text.startswith(":=", i):
            out.append(_Tok("op", ":="))
            i += 2
        elif ch in sy.SUPERSCRIPTS or ch in sy.SUBSCRIPTS:
            table, kind = (
                (sy.SUPERSCRIPTS, "sup") if ch in sy.SUPERSCRIPTS else (sy.SUBSCRIPTS, "sub")
            )
            j = i
            while j < len(text) and text[j] in table:
                j += 1
            inner = "".join(table[c] for c in text[i:j])
            out.append(_Tok("script", inner, kind, _lex(inner)))
            i = j
        else:
            out.append(_char_tok(ch))
            i += 1
    return out


def _char_tok(ch: str) -> _Tok:
    if ch in sy.GREEK:
        return _Tok("greek", ch)
    if ch in sy.LETTERLIKE:
        return _Tok("var", sy.LETTERLIKE[ch])
    if ch in sy.ACCENTS:
        return _Tok("accent", sy.ACCENTS[ch])
    if ch in "′″'":
        return _Tok("prime", "″" if ch == "″" else "′")
    if ch in OPEN:
        return _Tok("open", ch)
    if ch in CLOSE:
        return _Tok("close", ch)
    if ch == "|":
        return _Tok("bar", ch)
    if ch == "‖":
        return _Tok("dbar", ch)
    if ch in BIGOPS:
        return _Tok("bigop", ch)
    if ch == "√":
        return _Tok("sqrt", ch)
    if ch in "…⋯":
        return _Tok("dots", ch)
    if ch in sy.SYMBOLS or ch in sy.EXTRA or ch in ",;.:":
        return _Tok("op", ch)
    raise _Fail(ch)


class _Parser:
    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.pos = 0

    def peek(self) -> _Tok | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def row(self, stop: set[str] | None = None) -> Node:
        items: list[Node] = []
        while (t := self.peek()) is not None:
            if t.kind == "close" or (stop and t.kind in stop):
                break
            item = self.item(items[-1] if items else None)
            if (
                item.kind == "group"
                and item.text == "()"
                and items
                and items[-1].kind == "op"
                and items[-1].text in ("∈", "∉")
            ):
                item = _as_interval(item) or item
            items.append(item)
        return Node("row", list(items))

    def item(self, prev: Node | None) -> Node:
        node = self.atom(prev)
        while (t := self.peek()) is not None:
            if t.kind == "script":
                self.pos += 1
                node = _attach(node, t.script, Node("row", list(_Parser(t.inner).all())))
            elif t.kind == "prime" and node.kind != "op":
                self.pos += 1
                node = Node("prime", [node], t.text)
            elif t.kind == "accent" and node.kind != "op":
                self.pos += 1
                node = Node("accent", [node], t.text)
            elif t.kind == "open" and _applies(node):
                self.pos += 1
                node = Node("apply", [node, self.group(t.text)])
            else:
                break
        return node

    def all(self) -> list[Node]:
        node = self.row()
        if self.peek() is not None:
            raise _Fail("unbalanced")
        return [c for c in node.children if c is not None]

    def group(self, open_ch: str) -> Node:
        inner = self.row()
        t = self.peek()
        if t is None or t.kind != "close":
            raise _Fail("unclosed")
        self.pos += 1
        node = Node("group", [inner], open_ch + t.text)
        if open_ch + t.text in ("[]", "(]", "[)"):
            return _as_interval(node) or node
        return node

    def atom(self, prev: Node | None) -> Node:
        t = self.peek()
        assert t is not None
        self.pos += 1
        if t.kind in ("num", "var", "greek", "word", "op", "dots"):
            return Node(t.kind, [], t.text)
        if t.kind == "open":
            return self.group(t.text)
        if t.kind in ("bar", "dbar"):
            operand_start = prev is None or prev.kind == "op"
            if operand_start and self._has_closer(t.kind):
                inner = self.row(stop={t.kind})
                self.pos += 1
                return Node("abs" if t.kind == "bar" else "norm", [inner])
            return Node("op", [], "|" if t.kind == "bar" else "∥")
        if t.kind == "bigop":
            return Node(BIGOPS[t.text], [None, None], t.text)
        if t.kind == "sqrt":
            if self.peek() is None:
                raise _Fail("empty root")
            return Node("sqrt", [self.item(None)])
        raise _Fail(t.kind)

    def _has_closer(self, kind: str) -> bool:
        depth = 0
        for t in self.toks[self.pos :]:
            if t.kind == "open":
                depth += 1
            elif t.kind == "close":
                if depth == 0:
                    return False
                depth -= 1
            elif t.kind == kind and depth == 0:
                return True
        return False


def _applies(node: Node) -> bool:
    """A letter, Greek letter, function word, or one of them with scripts/primes, takes a group."""
    while node.kind in ("sub", "sup", "prime", "accent") and node.children:
        node = node.children[0]  # type: ignore[assignment]
    return node.kind in ("var", "greek", "word")


def _attach(base: Node, script: str, row: Node) -> Node:
    if base.kind in ("sum", "prod", "int"):
        kids = list(base.children)
        kids[0 if script == "sub" else 1] = row
        return Node(base.kind, kids, base.text)
    if base.kind == "word" and base.text in LIMOPS and script == "sub":
        return Node("limop", [row], base.text)
    if script == "sub" and base.kind == "sup" and base.children[0] is not None:
        # x^2_i is read x sub i, squared: the subscript goes on the base (spec §3c)
        return Node("sup", [Node("sub", [base.children[0], row]), base.children[1]])
    return Node(script, [base, row])


def _top_commas(row: Node) -> list[int]:
    return [i for i, c in enumerate(row.children) if c and c.kind == "op" and c.text == ","]


def _as_interval(group: Node) -> Node | None:
    inner = group.children[0]
    assert inner is not None
    commas = _top_commas(inner)
    if len(commas) != 1:
        return None
    k = commas[0]
    a, b = inner.children[:k], inner.children[k + 1 :]
    if not a or not b:
        return None
    return Node("interval", [Node("row", a), Node("row", b)], group.text)


def _runs_rows(span: MathSpan) -> list[list[tuple[str, str]]]:
    """Rows of (text, script) pieces from the span's runs; script is "", "sup" or "sub"."""
    runs = [r for r in span.runs if r.text]
    if not runs:
        return []
    base = max(r.size for r in runs)
    rows: list[list[tuple[str, str]]] = []
    row_y0 = row_mid = 0.0
    for r in runs:
        small = r.size < 0.85 * base
        if small or (r.superscript and rows):
            mid = (r.bbox.y0 + r.bbox.y1) / 2
            kind = "sup" if r.superscript or mid < row_mid else "sub"
            if not rows:
                raise _Fail("script without base")
            rows[-1].append((r.text, kind))
            continue
        if not rows or r.bbox.y0 > row_y0 + 0.5 * r.size:
            rows.append([])
            row_y0, row_mid = r.bbox.y0, (r.bbox.y0 + r.bbox.y1) / 2
        rows[-1].append((r.text, ""))
    return rows


def _row_tokens(pieces: list[tuple[str, str]]) -> list[_Tok]:
    out: list[_Tok] = []
    for text, script in pieces:
        if script:
            out.append(_Tok("script", text, script, _lex(text)))
        else:
            out.extend(_lex(text))
    return out


def _strip_label(toks: list[_Tok], label: str | None) -> list[_Tok]:
    if (
        label
        and len(toks) >= 3
        and toks[-3].text == "("
        and toks[-2].text == label
        and toks[-1].text == ")"
    ):
        return toks[:-3]
    return toks


def _matrix(rows: list[list[tuple[str, str]]]) -> Node | None:
    texts = ["".join(t for t, s in row if not s).strip() for row in rows]
    if not (texts[0][:1] in "[(" and texts[-1][-1:] in "])") or not texts[0] or not texts[-1]:
        return None
    texts[0], texts[-1] = texts[0][1:], texts[-1][:-1]
    cells = [t.split() for t in texts]
    if len({len(c) for c in cells}) != 1 or not cells[0]:
        return None
    out = [Node("row", [Node("row", _Parser(_lex(c)).all()) for c in row]) for row in cells]
    return Node("matrix", list(out))


def parse(span: MathSpan, text: str | None = None) -> Node | None:
    """The expression tree of ``span`` (module docstring), or None when it cannot structure.

    ``text`` is used instead of the runs when the span carries none (a clipped span)."""
    try:
        rows = _runs_rows(span) if span.runs else ([[(text, "")]] if text else [])
        if not rows:
            return None
        if len(rows) == 1:
            toks = _strip_label(_row_tokens(rows[0]), span.label)
            items = _Parser(toks).all()
            return Node("row", list(items)) if items else None
        if len(rows) > 2 or (rows[0] and rows[0][0][0].lstrip()[:1] in "[("):
            m = _matrix(rows)
            if m is not None or len(rows) > 2:
                return m
        top = _Parser(_row_tokens(rows[0])).all()
        den = _Parser(_strip_label(_row_tokens(rows[1]), span.label)).all()
        cut = max(
            (i for i, n in enumerate(top) if n.kind == "op" and n.text in RELATIONS), default=-1
        )
        num = top[cut + 1 :]
        if not num or not den:
            return None
        frac = Node("frac", [Node("row", list(num)), Node("row", list(den))])
        return Node("row", [*top[: cut + 1], frac])
    except _Fail:
        return None


def label_of(text: str) -> str | None:
    """ "3" from a display line ending in "(3)" (MATH-4)."""
    m = _LABEL_TAIL.search(text)
    return m.group(1) if m else None
