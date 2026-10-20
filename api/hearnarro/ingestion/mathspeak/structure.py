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

- a display set the TeX way (the left side on the maths axis, a numerator above it and a
  denominator below) is read on three levels: runs above the first run's row and the runs below
  them that follow are a ``frac`` inside the main row; runs under a CMEX underbrace are its label,
  read after a comma; a small script pair stacked on nothing (``½`` set in text style after ``=``)
  is a ``frac``; consecutive scripts of one kind are one script (``m_t`` then ``+1`` is ``m_{t+1}``);
- a run of three or more letters in an upright text font (``Update``, ``marg``, ``Stage``) is one
  word (``name``); CMEX hat and tilde glyphs, which precede their base, are accents.

``parse`` returns ``None`` when it cannot structure the span (an unknown character, unbalanced
brackets, a script with no base, three or more rows that are not a matrix). ``parse(...,
partial=True)`` never gives up on those: it keeps every sub-expression it can structure, closes an
unclosed group at the end, drops a stray closing bracket, and keeps an unknown character as a
symbol the reader names (MATH-1: the structured parts are spoken, the rest symbol by symbol).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
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
    kind: str  # num var greek word name op open close bar dbar bigop sqrt script prime accent
    text: str  # preaccent dots frac
    script: str = ""  # "sup" / "sub" for a script token
    inner: list[_Tok] = field(default_factory=list)
    inner2: list[_Tok] = field(default_factory=list)  # a frac token's denominator
    size: float = 0.0  # a script token's run size and centre, for a script of a script
    mid: float = 0.0


LIMOPS = {"lim", "max", "min", "sup", "inf", "argmin", "argmax"}
WORDS = {w for w in sy.FUNCTIONS if w.isascii() and len(w) > 1} | LIMOPS
RELATIONS = set(sy.CONVENTION["relations"]) | {"→", "⇒", "⟹", "⇔", "⟺", "↦"}
OPEN, CLOSE = "([{⟨", ")]}⟩"
BIGOPS = {"∑": "sum", "∏": "prod", "∫": "int", "∮": "int"}
_NUM = re.compile(r"\d+(?:\.\d+)?")
_LABEL_TAIL = re.compile(r"\s*\(\s*(\d+(?:\.\d+)*)\s*\)\s*$")
_LABEL_HEAD = re.compile(r"^\s*\(\s*(\d+(?:\.\d+)*)\s*\)\s+")  # left-numbered (amsmath leqno)
_PREACCENTS = {"ˆ": "hat", "˜": "tilde", "¯": "bar"}  # spacing accents set before their base
_SAME = {
    "∆": "Δ", "µ": "μ", "⋆": "∗", "−→": "→", "−−→": "→", "←−": "←", "7→": "↦", ": =": ":=",
    "–": "−",  # an en dash between operands, as text fonts set minus
}  # fmt: skip
_POWER = re.compile(r"\*\*\s*(\d+(?:\.\d+)?|[A-Za-z])")
_CAMEL = re.compile(r"([a-z]{2,})([A-Z]{2,}s?)")
_MATH_FONTS = ("cmmi", "cmsy", "cmex", "msbm", "msam", "cmbsy", "eufm", "rsfs", "math", "italic")


class _Lenient:
    """Set while a ``partial`` parse runs: unknown characters lex as symbols."""

    on = False


def _upright(font: str) -> bool:
    """A text font (CMR, Times, ...), where a run of letters is a word, not juxtaposed letters."""
    f = font.lower()
    return bool(f) and not any(m in f for m in _MATH_FONTS)


def _is_name(run: str) -> bool:
    return len(run) >= 3 and (run.islower() or (run[0].isupper() and run[1:].islower()))


def _lex(text: str, words: bool = False) -> list[_Tok]:
    """Tokens of ``text``; ``words`` (an upright text font) reads letter runs as words."""
    for a, b in _SAME.items():
        text = text.replace(a, b)
    # Mathematical alphanumerics (𝑥, 𝑙𝑜𝑔, 𝐀; unicode-math fonts put them in the text layer) are
    # their plain letters and digits, so 𝑙𝑜𝑔 is the function word log (m5 p3k, MATH-1).
    text = "".join(
        unicodedata.normalize("NFKC", c) if 0x1D400 <= ord(c) <= 0x1D7FF else c for c in text
    )
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
            camel = _CAMEL.fullmatch(run)
            if camel:
                # "ofSTDEV": a word and an acronym set as one italic identifier read as words
                out.extend(_Tok("name", g.lower()) for g in camel.groups() if g)
            elif len(run) >= 5 and run.isupper():
                out.append(_Tok("name", run.lower()))  # STDEV: an identifier, not five letters
            elif run in WORDS:
                out.append(_Tok("word", run))
            elif len(run) <= 4 and run[0].isupper() and run.lower() in WORDS:
                out.append(_Tok("word", run.lower()))  # Tr, Var as set in papers
            elif words and _is_name(run):
                out.append(_Tok("name", run.lower()))
            else:
                out.extend(_Tok("var", c) for c in run)
            i = j
        elif text.startswith("...", i):
            out.append(_Tok("dots", "…"))
            i += 3
        elif text.startswith("|||", i):
            out.append(_Tok("tbar", "|||"))  # the operator norm |||A|||
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
        elif text.startswith("**", i) and (m := _POWER.match(text, i)):
            inner = m.group(1)  # Python's power in prose maths: y**2
            out.append(_Tok("script", inner, "sup", _lex(inner)))
            i = m.end()
        elif (
            ch == "¯"
            and out
            and out[-1].kind in ("var", "greek")
            and not text[i + 1 : i + 2].isalpha()
        ):
            out.append(_Tok("accent", "bar"))  # a text font sets the macron after its letter: x¯
            i += 1
        elif ch in _PREACCENTS:
            out.append(_Tok("preaccent", _PREACCENTS[ch]))
            i += 1
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
    if ch == "#":
        return _Tok("op", ch)  # "# of x": the number of x
    if ch in "‖∥":
        return _Tok("dbar", ch)
    if ch in BIGOPS:
        return _Tok("bigop", ch)
    if ch == "√":
        return _Tok("sqrt", ch)
    if ch == "⁄":
        return _Tok("op", ch)  # U+2044 FRACTION SLASH: a drawn bar (Parser.item)
    if ch in "…⋯":
        return _Tok("dots", ch)
    if ch in sy.SYMBOLS or ch in sy.EXTRA or ch in ",;.:":
        return _Tok("op", ch)
    if _Lenient.on:
        return _Tok("op", ch)
    raise _Fail(ch)


class _Parser:
    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.pos = 0
        self.lenient = _Lenient.on

    def peek(self) -> _Tok | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def row(self, stop: set[str] | None = None) -> Node:
        items: list[Node] = []
        while (t := self.peek()) is not None:
            if t.kind == "close" or (stop and t.kind in stop):
                break
            if t.kind == "script" and (not items or items[-1].kind == "op"):
                items.append(self.loose_script())
                continue
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

    def loose_script(self) -> Node:
        """A script with no base: a stacked small pair is a fraction (``½`` after ``=``), a lone
        one is read as its content."""
        t = self.toks[self.pos]
        self.pos += 1
        nxt = self.peek()
        if nxt is not None and nxt.kind == "script" and nxt.script != t.script:
            self.pos += 1
            num, den = (t, nxt) if t.script == "sup" else (nxt, t)
            return Node("frac", [self.sub_row(num.inner), self.sub_row(den.inner)])
        if not self.lenient:
            raise _Fail("script without base")
        return self.sub_row(t.inner)

    def sub_row(self, toks: list[_Tok]) -> Node:
        p = _Parser(toks)
        return Node("row", list(p.all()))

    def item(self, prev: Node | None) -> Node:
        node = self.atom(prev)
        while (t := self.peek()) is not None:
            if t.kind == "script" and node.kind == "op":
                break  # a script after an operator has no base (``loose_script``)
            if t.kind == "script":
                self.pos += 1
                if t.inner and all(x.kind == "prime" for x in t.inner):
                    node = Node("prime", [node], t.inner[0].text)  # a prime set as a script
                else:
                    node = _attach(node, t.script, self.sub_row(t.inner))
            elif t.kind == "prime" and node.kind != "op":
                self.pos += 1
                node = Node("prime", [node], t.text)
            elif t.kind == "accent" and node.kind != "op":
                self.pos += 1
                node = Node("accent", [node], t.text)
            elif t.kind == "open" and t.text == "(" and _operator_group(node):
                self.pos += 1
                node = Node("apply", [node, self.group(t.text)])  # (μP)(A) "mu p of a"
            elif t.kind == "open" and _applies(node) and not self._product(node):
                self.pos += 1
                node = Node("apply", [node, self.group(t.text)])
            elif t.kind == "op" and t.text == "⁄" and self.pos + 1 < len(self.toks):
                self.pos += 1  # (num)⁄(den), a drawn fraction bar (extract.vector_maths)
                den = self.item(None)
                node = Node("frac", [_ungroup(node), _ungroup(den)])
            else:
                break
        return node

    def all(self) -> list[Node]:
        out: list[Node] = []
        while True:
            out.extend(c for c in self.row().children if c is not None)
            if self.peek() is None:
                return out
            if not self.lenient:
                raise _Fail("unbalanced")
            self.pos += 1  # a stray closing bracket (its opener is on another line)

    def group(self, open_ch: str) -> Node:
        inner = self.row()
        t = self.peek()
        if t is None or t.kind != "close":
            if not self.lenient:
                raise _Fail("unclosed")
            return Node(
                "group", [inner], open_ch + {"(": ")", "[": "]", "{": "}"}.get(open_ch, ")")
            )
        self.pos += 1
        node = Node("group", [inner], open_ch + t.text)
        if open_ch + t.text in ("[]", "(]", "[)"):
            return _as_interval(node) or node
        return node

    def atom(self, prev: Node | None) -> Node:
        t = self.peek()
        assert t is not None
        self.pos += 1
        if t.kind in ("num", "var", "greek", "word", "name", "op", "dots"):
            return Node(t.kind, [], t.text)
        if t.kind == "frac":
            return Node("frac", [self.sub_row(t.inner), self.sub_row(t.inner2)])
        if t.kind == "preaccent":
            if self.peek() is None or self.peek().kind in ("close", "op"):  # type: ignore[union-attr]
                return Node("op", [], "")
            return Node("accent", [self.atom(prev)], t.text)
        if t.kind == "open":
            return self.group(t.text)
        if t.kind in ("bar", "dbar"):
            # a norm also opens after a letter (E‖x‖); a single ∥ inside D(p ∥ q) has no closer
            operand_start = (
                prev is None
                or prev.kind in ("op", "limop", "sum", "prod", "int")
                or (t.kind == "dbar" and prev.kind != "group")
                or (prev.kind in ("var", "greek") and self._closes_flat(t.kind))
            )
            if operand_start and self._has_closer(t.kind):
                inner = self.row(stop={t.kind})
                self.pos += 1
                return Node("abs" if t.kind == "bar" else "norm", [inner])
            return Node("op", [], "|" if t.kind == "bar" else "∥")
        if t.kind == "tbar":
            if self._has_closer("tbar"):
                inner = self.row(stop={"tbar"})
                self.pos += 1
                return Node("opnorm", [inner])
            return Node("op", [], "∥")
        if t.kind == "bigop":
            return Node(BIGOPS[t.text], [None, None], t.text)
        if t.kind == "sqrt":
            if self.peek() is None or self.peek().kind == "close":  # type: ignore[union-attr]
                if not self.lenient:
                    raise _Fail("empty root")
                return Node("op", [], "√")
            return Node("sqrt", [self.item(None)])
        if self.lenient and t.kind == "script":
            return self.sub_row(t.inner)  # a script with nothing to attach to
        if self.lenient:
            return Node("op", [], t.text)  # a prime with nothing to attach to
        raise _Fail(t.kind)

    def _product(self, node: Node) -> bool:
        """``d(log N)``: a single letter before a group that opens with a function word is a
        product, not a function application."""
        nxt = self.toks[self.pos + 1] if self.pos + 1 < len(self.toks) else None
        return node.kind == "var" and nxt is not None and nxt.kind == "word"

    def _closes_flat(self, kind: str) -> bool:
        """``E|R_n|``: after a letter a bar opens an absolute value only when its closer comes
        before any relation or conditional bar of the enclosing group, so ``p(y | x)`` and
        ``E[D | F]`` keep "given"."""
        depth = 0
        for t in self.toks[self.pos :]:
            if t.kind == "open":
                depth += 1
            elif t.kind == "close":
                if depth == 0:
                    return False
                depth -= 1
            elif depth == 0 and t.kind == kind:
                return True
            elif depth == 0 and t.kind == "op" and t.text in RELATIONS:
                return False
        return False

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


def _ungroup(node: Node) -> Node:
    """A fraction part: ``(a + b)`` is the row ``a + b``; a single item is a one-item row."""
    if node.kind == "group" and node.text == "()" and node.children[0] is not None:
        return node.children[0]
    return Node("row", [node])


def _applies(node: Node) -> bool:
    """A letter, Greek letter, function word, or one of them with scripts/primes, takes a group."""
    while node.kind in ("sub", "sup", "prime", "accent") and node.children:
        node = node.children[0]  # type: ignore[assignment]
    return node.kind in ("var", "greek", "word", "name")


def _operator_group(node: Node) -> bool:
    """``(μP)``: a parenthesized product of two or three letters, one a Latin capital, is an
    operator (a measure composed with a kernel), so a group after it is its argument."""
    if node.kind != "group" or node.text != "()" or node.children[0] is None:
        return False
    kids = [c for c in node.children[0].children if c is not None]
    return (
        2 <= len(kids) <= 3
        and all(c.kind in ("var", "greek") for c in kids)
        and any(c.kind == "var" and c.text.isupper() for c in kids)
    )


def _attach(base: Node, script: str, row: Node) -> Node:
    if base.kind in ("sum", "prod", "int"):
        kids = list(base.children)
        k = 0 if script == "sub" else 1
        old = kids[k]
        kids[k] = Node("row", [*old.children, *row.children]) if old is not None else row
        return Node(base.kind, kids, base.text)
    if base.kind == "word" and base.text in LIMOPS and script == "sub":
        return Node("limop", [row], base.text)
    if base.kind == "limop" and script == "sub" and base.children[0] is not None:
        return Node("limop", [Node("row", [*base.children[0].children, *row.children])], base.text)
    if script == "sub" and base.kind == "sup" and base.children[0] is not None:
        # x^2_i is read x sub i, squared: the subscript goes on the base (spec §3c)
        return Node("sup", [Node("sub", [base.children[0], row]), base.children[1]])
    if base.kind == script and base.children[1] is not None:
        # two runs of one script kind are one script: m_t then +1 is m_{t+1}, p^⊗ then n is p^{⊗n}
        joined = Node("row", [*base.children[1].children, *row.children])
        return Node(script, [base.children[0], joined])
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


# TeX's CMEX extension font (large delimiters, operators, radicals): PDFs made by TeX expose its
# glyphs under their code points, so "P" is a summation sign and "\x00" a big left parenthesis.
# Control characters never occur in text, so they are read as CMEX delimiters in any run.
_CMEX_DELIMS = dict(
    zip(
        range(0x24),
        "()[]⌊⌋⌈⌉{}⟨⟩|‖/\\()()[]⌊⌋⌈⌉{}⟨⟩/\\()[]",
        strict=True,
    )
)
_CMEX_LETTERS = {
    "P": "∑", "X": "∑", "Q": "∏", "Y": "∏", "R": "∫", "Z": "∫",
    "H": "∮", "I": "∮", "p": "√", "q": "√", "r": "√", "s": "√", "t": "√",
    "b": "ˆ", "c": "ˆ", "d": "ˆ", "e": "˜", "f": "˜", "g": "˜",  # widehat, widetilde
    "h": "[", "i": "]", "j": "⌊", "k": "⌋", "l": "⌈", "m": "⌉", "n": "{", "o": "}",
    "D": "⟨", "E": "⟩", "N": "⊗", "O": "⊗", "L": "⊕", "M": "⊕", "J": "⊙", "K": "⊙",
}  # fmt: skip
_UNDERBRACE = set("z{|}")  # CMEX brace pieces (0x7A-0x7D): an underbrace drawn in parts
_CONTROL_DELIMS = str.maketrans({chr(k): v for k, v in _CMEX_DELIMS.items() if k < 0x20})
_TEXT_ACCENTS = {"\x16": "¯", "^": "ˆ", "~": "˜"}  # CMR accent glyphs set alone in a run


def cmex_text(text: str, font: str = "") -> str:
    """``text`` with CMEX code points read as the delimiters and operators they draw."""
    f = font.lower()
    if "cmex" in f:
        if text.strip() and set(text.strip()) - {" "} <= _UNDERBRACE and "z" in text:
            return ""  # an underbrace: its label is read by ``_runs_rows``
        table = {**_CMEX_LETTERS, **{chr(k): v for k, v in _CMEX_DELIMS.items() if k >= 0x21}}
        text = "".join(table.get(c, c) for c in text)
    elif f.startswith(("cmr", "cmbx", "cmti", "cmss")) and text.strip() in _TEXT_ACCENTS:
        return _TEXT_ACCENTS[text.strip()]
    return text.translate(_CONTROL_DELIMS)


def _is_underbrace(r: Any) -> bool:
    t = r.text.strip()
    return "cmex" in r.font.lower() and bool(t) and set(t) - {" "} <= _UNDERBRACE and "z" in t


def _base_size(runs: list[Any]) -> float:
    """The body size of a display: the largest size outside CMEX, whose large delimiters and
    operators would otherwise make every other run look like a script."""
    sizes = [r.size for r in runs if "cmex" not in r.font.lower()]
    return max(sizes) if sizes else max(r.size for r in runs)


Piece = tuple[str, str, str] | _Tok  # (text, script "" / "sup" / "sub", font) or a built token


def _mid(r: Any) -> float:
    return float((r.bbox.y0 + r.bbox.y1) / 2)


def _pieces(runs: list[Any], base: float, rows: bool = True) -> list[list[Piece]]:
    """Rows of pieces; a small run is a script, "sup" when its centre sits above the last base
    run's centre (or its superscript flag is set), else "sub". With ``rows`` False every
    full-size run stays on one row (the parts of a three-level display)."""
    out: list[list[Piece]] = []
    row_y0 = last_mid = 0.0
    for r in runs:
        text = cmex_text(r.text, r.font)
        if not text:
            continue
        small = r.size < 0.85 * base
        if small or (r.superscript and out):
            if not out:
                if not _Lenient.on:
                    raise _Fail("script without base")
                out.append([])
            prev = out[-1][-1] if out[-1] else None
            if isinstance(prev, _Tok) and prev.kind == "script" and r.size < 0.85 * prev.size:
                # a script of a script (K_2 in an exponent, π_n under an E)
                kind = "sup" if _mid(r) < prev.mid - 0.15 * prev.size else "sub"
                toks = _lex(text, _upright(r.font))
                last = prev.inner[-1] if prev.inner else None
                if last is not None and last.kind == "script" and last.script == kind:
                    last.inner.extend(toks)  # one nested script set in several runs
                else:
                    prev.inner.append(_Tok("script", text, kind, toks))
                continue
            kind = "sup" if r.superscript or _mid(r) < last_mid else "sub"
            words = _upright(r.font)
            out[-1].append(_Tok("script", text, kind, _lex(text, words), [], r.size, _mid(r)))
            continue
        if not out or (rows and r.bbox.y0 > row_y0 + 0.5 * r.size):
            out.append([])
            row_y0 = r.bbox.y0
        if "cmex" not in r.font.lower() or text in BIGOPS:
            last_mid = _mid(r)  # a large operator's limits sit above or below its centre
        out[-1].append((text, "", r.font))
    return out


def _flat_pieces(runs: list[Any]) -> list[Piece]:
    if not runs:
        return []
    rows = _pieces(runs, _base_size(runs), rows=False)
    return [p for row in rows for p in row]


def _runs_rows(span: MathSpan) -> list[list[Piece]]:
    """Rows of pieces from the span's runs (``_pieces``), with a three-level display's
    fractions and an underbrace's label folded into the main row (module docstring)."""
    runs = [r for r in span.runs if r.text]
    if not runs:
        return []
    base = _base_size(runs)
    full = [r for r in runs if r.size >= 0.85 * base and "cmex" not in r.font.lower()]
    has_brace = any(_is_underbrace(r) for r in runs)
    if not full:
        return _pieces(runs, base)
    main_y0 = full[0].bbox.y0
    tol = 0.4 * base
    above = any(r.bbox.y0 < main_y0 - tol for r in full)
    if not above and not has_brace:
        return _pieces(runs, base)
    main_mid = _mid(full[0])
    runs = _limits_after(runs, base)
    frac_x1 = 0.0  # right edge of the current fraction's full-size runs
    row: list[Piece] = []
    chunk: list[Any] = []
    num: list[Any] = []
    den: list[Any] = []
    label: list[Any] = []
    mode = "main"  # main / frac / label

    def flush() -> None:
        nonlocal mode, chunk, num, den, label
        row.extend(_flat_pieces(chunk))
        if mode == "frac" and num and den:
            n, d = _row_tokens(_flat_pieces(num)), _row_tokens(_flat_pieces(den))
            row.append(_Tok("frac", "", "", n, d))
        elif mode == "frac":
            row.extend(_flat_pieces(num + den))
        elif mode == "label" and label:
            row.append(_Tok("op", ","))
            row.extend(_flat_pieces(label))
        chunk, num, den, label, mode = [], [], [], [], "main"

    for r in runs:
        is_full = r.size >= 0.85 * base and "cmex" not in r.font.lower()
        if _is_underbrace(r):
            flush()
            mode = "label"
            continue
        if mode == "label":
            if is_full and abs(r.bbox.y0 - main_y0) <= tol:
                flush()
                chunk.append(r)
            else:
                label.append(r)
            continue
        if mode == "frac" and not is_full and den and r.bbox.x0 >= frac_x1 - 0.5:
            flush()  # a script or large operator right of the bar is back on the main row
            chunk.append(r)
            continue
        if is_full and r.bbox.y0 < main_y0 - tol:
            if mode == "frac" and den:
                flush()
            rel = _RELATION_HEAD.match(r.text)
            if rel and rel.end() < len(r.text.rstrip()):
                # ":= 1" set as one run: the relation is on the main row, "1" is the numerator
                chunk.append(replace(r, text=rel.group(0)))
                r = replace(r, text=r.text[rel.end() :])
            if mode != "frac":
                row.extend(_flat_pieces(chunk))
                chunk, mode, frac_x1 = [], "frac", 0.0
            num.append(r)
            frac_x1 = max(frac_x1, r.bbox.x1)
        elif mode == "frac" and is_full and r.bbox.y0 > main_y0 + tol:
            den.append(r)
            frac_x1 = max(frac_x1, r.bbox.x1)
        elif mode == "frac" and not is_full:
            (num if _mid(r) < main_mid and not den else den).append(r)
        else:
            if mode == "frac":
                flush()
            chunk.append(r)
    flush()
    return [row]


_RELATION_HEAD = re.compile(r"\s*(:=|=|≡|≈|≤|≥|<|>)\s*")


def _limits_after(runs: list[Any], base: float) -> list[Any]:
    """Runs with each stacked limit (a small run centred over or under a CMEX large operator)
    moved to just after that operator, so it attaches as the operator's limit (``sum``)."""
    ops = [r for r in runs if "cmex" in r.font.lower() and cmex_text(r.text, r.font) in BIGOPS]
    if not ops:
        return runs
    out = [r for r in runs]
    for op in ops:
        lims = [
            r
            for r in runs
            if r is not op
            and r.size < 0.85 * base
            and op.bbox.x0 - 1.0 <= (r.bbox.x0 + r.bbox.x1) / 2 <= op.bbox.x1 + 1.0
            and (r.bbox.y1 <= _mid(op) or r.bbox.y0 >= _mid(op))
        ]
        if not lims:
            continue
        out = [r for r in out if not any(r is x for x in lims)]
        at = next(i for i, r in enumerate(out) if r is op) + 1
        out[at:at] = lims
    return out


def _row_tokens(pieces: list[Piece]) -> list[_Tok]:
    out: list[_Tok] = []
    for p in pieces:
        if isinstance(p, _Tok):
            out.append(p)
            continue
        text, script, font = p
        words = _upright(font)
        if script:
            out.append(_Tok("script", text, script, _lex(text, words)))
        else:
            out.extend(_lex(text, words))
    for i in range(len(out) - 1, 0, -1):  # ":" and "=" set in two runs are one ":="
        if out[i].kind == "op" and out[i].text == "=" and out[i - 1].text == ":":
            out[i - 1 : i + 1] = [_Tok("op", ":=")]
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
    if label and len(toks) > 3 and [t.text for t in toks[:3]] == ["(", label, ")"]:
        return toks[3:]  # left-numbered display (MATH-4)
    return toks


def _matrix(rows: list[list[Piece]]) -> Node | None:
    texts = [
        "".join(p[0] for p in row if not isinstance(p, _Tok) and not p[1]).strip() for row in rows
    ]
    if not (texts[0][:1] in "[(" and texts[-1][-1:] in "])") or not texts[0] or not texts[-1]:
        return None
    texts[0], texts[-1] = texts[0][1:], texts[-1][:-1]
    cells = [t.split() for t in texts]
    if len({len(c) for c in cells}) != 1 or not cells[0]:
        return None
    out = [Node("row", [Node("row", _Parser(_lex(c)).all()) for c in row]) for row in cells]
    return Node("matrix", list(out))


def parse(span: MathSpan, text: str | None = None, *, partial: bool = False) -> Node | None:
    """The expression tree of ``span`` (module docstring), or None when it cannot structure.

    ``text`` is used instead of the runs when the span carries none (a clipped span).
    ``partial`` keeps what can be structured instead of returning None (module docstring)."""
    _Lenient.on = partial
    try:
        return _parse(span, text)
    except _Fail:
        return None
    finally:
        _Lenient.on = False


def _parse(span: MathSpan, text: str | None) -> Node | None:
    # a span without runs (a content or glyph span) is text-font maths: a lower-case run of three
    # or more letters is a word or label ("∆subopt"), as in an upright run
    rows = _runs_rows(span) if span.runs else ([[(cmex_text(text), "", "text")]] if text else [])
    if not rows:
        return None
    if len(rows) > 2 and _Lenient.on and _matrix(rows) is None:
        rows = [[p for row in rows for p in row]]  # read the lines one after another
    if len(rows) == 1:
        toks = _strip_label(_row_tokens(rows[0]), span.label)
        items = _Parser(toks).all()
        return Node("row", list(items)) if items else None
    first = rows[0][0] if rows[0] else None
    if len(rows) > 2 or (isinstance(first, tuple) and first[0].lstrip()[:1] in "[("):
        m = _matrix(rows)
        if m is not None or len(rows) > 2:
            return m
    top = _Parser(_strip_label(_row_tokens(rows[0]), span.label)).all()
    den = _Parser(_strip_label(_row_tokens(rows[1]), span.label)).all()
    if not _stacked(span.runs):
        return Node("row", [*top, *den])  # a display continued on a second line (align)
    cut = max((i for i, n in enumerate(top) if n.kind == "op" and n.text in RELATIONS), default=-1)
    num = top[cut + 1 :]
    if not num or not den:
        return None
    frac = Node("frac", [Node("row", list(num)), Node("row", list(den))])
    return Node("row", [*top[: cut + 1], frac])


def _stacked(runs: list[Any]) -> bool:
    """Two rows are a fraction only when the second sits under the first's numerator: it starts
    no further left than the text after the first row's last relation, and ends no further right
    than the first row. A second line that starts left of that is a continued display."""
    runs = [r for r in runs if r.text.strip() and hasattr(r.bbox, "x0")]
    if not runs:
        return True
    base = _base_size(runs)
    full = [r for r in runs if r.size >= 0.85 * base and "cmex" not in r.font.lower()]
    if not full:
        return True
    y0 = full[0].bbox.y0
    top = [r for r in full if r.bbox.y0 <= y0 + 0.5 * r.size]
    low = [r for r in full if r.bbox.y0 > y0 + 0.5 * r.size]
    if not low:
        return True
    cut = max((i for i, r in enumerate(top) if any(c in RELATIONS for c in r.text)), default=-1)
    num = top[cut + 1 :] or top
    tol = 0.6 * base
    return bool(
        min(r.bbox.x0 for r in low) >= min(r.bbox.x0 for r in num) - tol
        and max(r.bbox.x1 for r in low) <= max(r.bbox.x1 for r in top) + tol
    )


def label_of(text: str) -> str | None:
    """ "3" from a display line ending in "(3)", or starting with it when the document numbers
    equations on the left (MATH-4)."""
    m = _LABEL_TAIL.search(text) or _LABEL_HEAD.match(text)
    return m.group(1) if m else None
