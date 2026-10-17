"""English for an expression tree, in the one convention of spec §3c (MATH-1..3, D36).

ClearSpeak-style plain English, lower case: letters are read as letters, juxtaposition is silent,
grouping brackets are silent, relations carry "is" except inside a subscript condition, scripts
are "sub" / "squared" / "cubed" / "to the n" / "transpose" / "star" / "sup <label>", stacked
fractions with one-token parts are "a over b" and longer ones "the fraction ... over ..., end
fraction", large operators read their limits ("the sum from i equals 1 to n of"), intervals are
"the interval from a to b" (with "exclusive" on an open end). Commas are prosody only.

``fallback`` is MATH-1's never-silent reading: "equation N" (or "equation") then every symbol
left to right by ``symbols.name_of``.
"""

from __future__ import annotations

from hearnarro.ingestion.mathspeak import symbols as sy
from hearnarro.ingestion.mathspeak.structure import RELATIONS, MathSpan, Node, label_of

_LIMOP_WORDS = {
    "lim": "the limit",
    "max": "the maximum",
    "min": "the minimum",
    "sup": "the supremum",
    "inf": "the infimum",
    "argmin": "the arg min",
    "argmax": "the arg max",
}
_NUMERIC_FRACTIONS = {
    ("1", "2"): "1 half",
    ("1", "3"): "1 third",
    ("2", "3"): "2 thirds",
    ("1", "4"): "1 fourth",
    ("3", "4"): "3 fourths",
}
_ATTACH = {",", ";"}


def _flat(node: Node | None) -> str:
    if node is None:
        return ""
    if not node.children:
        return node.text
    return "".join(_flat(c) for c in node.children)


def _join(words: list[str]) -> str:
    out: list[str] = []
    for w in words:
        if not w:
            continue
        if w in _ATTACH and out:
            out[-1] += w
        else:
            out.append(w)
    return " ".join(out)


class _Reader:
    def __init__(self, intervals: bool) -> None:
        self.intervals = intervals

    def row(self, node: Node | None, *, limit: bool = False, setbuilder: bool = False) -> list[str]:
        items = [c for c in (node.children if node else []) if c is not None]
        words: list[str] = []
        colon_seen = False
        prev: Node | None = None
        i = 0
        while i < len(items):
            it = items[i]
            nxt = items[i + 2] if i + 2 < len(items) else None
            if (
                it.kind == "num"
                and nxt is not None
                and nxt.kind == "num"
                and items[i + 1].kind == "op"
                and items[i + 1].text == "/"
                and (it.text, nxt.text) in _NUMERIC_FRACTIONS
            ):
                words.append(_NUMERIC_FRACTIONS[(it.text, nxt.text)])
                prev, i = nxt, i + 3
                continue
            if it.kind == "op":
                words.append(self.op(it.text, items[i + 1 :], colon_seen, limit, setbuilder))
                colon_seen = colon_seen or it.text == ":"
            else:
                if (
                    it.kind in ("group", "abs")
                    and prev is not None
                    and prev.kind in ("num", "group")
                ):
                    words.append("times")  # 2(k - 1): a parenthesized factor, not an argument
                words.extend(self.item(it, limit=limit))
            prev, i = it, i + 1
        return words

    def op(
        self, sym: str, rest: list[Node], colon_seen: bool, limit: bool, setbuilder: bool
    ) -> str:
        if sym in _ATTACH:
            return sym
        if sym == ".":
            return ""
        if sym == ":":
            if setbuilder:
                return "such that"
            return "from" if any(n.kind == "op" and n.text == "→" for n in rest) else "such that"
        if sym == "→":
            return "to" if colon_seen else "approaches"
        if sym == "|":
            return "such that" if setbuilder else "given"
        word = sy.name_of(sym) or ""
        if limit and sym in RELATIONS and word.startswith("is "):
            word = word[3:]
        return word

    def item(self, n: Node, *, limit: bool = False) -> list[str]:
        k, kids = n.kind, n.children
        if k == "row":
            return self.row(n, limit=limit)
        if k == "num":
            return [n.text]
        if k == "var":
            return [n.text.lower()]
        if k in ("greek", "dots"):
            return [sy.name_of(n.text) or ""]
        if k == "op":
            return [self.op(n.text, [], False, limit, False)]
        if k == "word":
            if n.text in _LIMOP_WORDS:
                return [_LIMOP_WORDS[n.text], "of"]
            return [sy.FUNCTIONS.get(n.text, n.text)]
        if k == "sup":
            return self.sup(kids[0], kids[1], limit)
        if k == "sub":
            return [*self.item(kids[0], limit=limit), "sub", *self.script(kids[1])]  # type: ignore[arg-type]
        if k == "prime":
            return [*self.item(kids[0]), "double prime" if n.text == "″" else "prime"]  # type: ignore[arg-type]
        if k == "accent":
            base = self.item(kids[0])  # type: ignore[arg-type]
            return ["vector", *base] if n.text == "vector" else [*base, n.text]
        if k == "frac":
            num, den = self.row(kids[0], limit=limit), self.row(kids[1], limit=limit)
            if all(
                len(c.children) == 1 and c.children[0] and not c.children[0].children
                for c in kids
                if c is not None
            ):
                return [*num, "over", *den]
            return ["the fraction", *num, "over", *den, ",", "end fraction"]
        if k == "sqrt":
            return ["the square root of", *self.item(kids[0])]  # type: ignore[arg-type]
        if k in ("sum", "prod", "int"):
            name = sy.SYMBOLS[n.text]
            lo, hi = kids
            if lo is not None and hi is not None:
                return [name, "from", *self.script(lo), "to", *self.script(hi), "of"]
            if lo is not None:
                return [name, "over", *self.script(lo), "of"]
            return [name, "of"]
        if k == "limop":
            word = _LIMOP_WORDS[n.text]
            sub = self.script(kids[0])
            return [word, "as" if n.text == "lim" else "over", *sub, "of"]
        if k == "apply":
            return self.apply(kids[0], kids[1])  # type: ignore[arg-type]
        if k == "group":
            return self.group(n)
        if k == "interval":
            a, b = self.row(kids[0]), self.row(kids[1])
            if not self.intervals:
                return [*a, ",", *b]
            if n.text == "[]":
                return ["the interval from", *a, "to", *b]
            if n.text == "(]":
                return ["the interval from", *a, ",", "exclusive", ",", "to", *b]
            if n.text == "[)":
                return ["the interval from", *a, "to", *b, ",", "exclusive"]
            return ["the open interval from", *a, "to", *b]
        if k == "abs":
            return ["the absolute value of", *self.row(kids[0])]
        if k == "norm":
            return ["the norm of", *self.row(kids[0])]
        if k == "matrix":
            words = ["the matrix with rows:"]
            for r, row in enumerate(c for c in kids if c is not None):
                if r:
                    words.append(";")
                for j, cell in enumerate(c for c in row.children if c is not None):
                    if j:
                        words.append(",")
                    words.extend(self.row(cell))
            return words
        return [sy.name_of(n.text) or ""]

    def script(self, row: Node | None) -> list[str]:
        flat = _flat(row)
        if len(flat) >= 3 and flat.isascii() and flat.isalpha() and flat.islower():
            return [flat]  # x_{emp}: a word or abbreviation is read as a word
        return self.row(row, limit=True)

    def sup(self, base: Node | None, script: Node | None, limit: bool) -> list[str]:
        words = self.item(base, limit=limit) if base is not None else []
        if base is not None and base.kind in ("group", "apply", "abs", "norm", "interval", "sub"):
            words.append(",")  # a comma closes a group (or a subscript) before a power
        flat = _flat(script)
        kids = [c for c in (script.children if script else []) if c is not None]
        if flat == "2":
            return [*words, "squared"]
        if flat == "3":
            return [*words, "cubed"]
        if flat in ("T", "⊤"):
            return [*words, "transpose"]
        if flat in ("*", "∗"):
            return [*words, "star"]
        if flat in ("′", "″"):
            return [*words, "prime" if flat == "′" else "double prime"]
        if len(kids) == 1 and kids[0].kind == "group" and kids[0].text == "()":
            return [*words, "sup", *self.row(kids[0].children[0])]
        if len(flat) >= 3 and flat.isascii() and flat.isalpha() and flat.islower():
            return [*words, "sup", flat]
        if kids and kids[0].kind == "op" and kids[0].text == "⊗":
            return [*words, "to the tensor power", *self.row(Node("row", list(kids[1:])))]
        return [*words, "to the", *self.row(script)]

    def apply(self, fn: Node, group: Node) -> list[str]:
        inner = group.children[0]
        args = self.row(inner)
        if fn.kind == "word" and fn.text in _LIMOP_WORDS:
            return [_LIMOP_WORDS[fn.text], "of", *self._and(inner, args)]
        if fn.kind == "limop":
            return [*self.item(fn)[:-1], "of", *args]
        word = sy.FUNCTIONS.get(fn.text) if fn.kind == "word" else None
        if word and word.endswith(" of"):
            return [word, *args]  # det, tr, Var, Cov: "the variance of x"
        return [*self.item(fn), "of", *args]

    def _and(self, inner: Node | None, args: list[str]) -> list[str]:
        if inner is not None and sum(1 for c in inner.children if c and c.text == ",") == 1:
            return ["and" if w == "," else w for w in args]
        return args

    def group(self, n: Node) -> list[str]:
        inner = n.children[0]
        if n.text == "{}":
            parts = [c for c in (inner.children if inner else []) if c is not None]
            cut = next(
                (i for i, c in enumerate(parts) if c.kind == "op" and c.text in ("|", ":")), None
            )
            if cut is not None:
                return ["the set of", *self.row(inner, setbuilder=True)]
            return ["the set", *self.row(inner)]
        if n.text == "⟨⟩":
            return ["the inner product of", *self._and(inner, self.row(inner))]
        return self.row(inner)


def speak(node: Node, *, intervals: bool = True) -> str:
    """English for ``node`` (§3c). ``intervals`` False reads a bracket pair as a list (prose)."""
    return _join(_Reader(intervals).item(node))


def _span_text(span: MathSpan) -> str:
    return "".join(r.text for r in span.runs)


def fallback(span: MathSpan, text: str | None = None) -> str:
    """MATH-1: "equation N" (or "equation") then every symbol left to right by name; never empty."""
    raw = text if text is not None else _span_text(span)
    label = span.label or label_of(raw)
    words = ["equation", label] if label else ["equation"]
    if label:
        raw = raw[: raw.rfind("(")] if "(" in raw else raw
    for ch in raw:
        if not ch.isspace():
            name = sy.name_of(ch) or sy.ACCENTS.get(ch)
            if name:
                words.append(name)
    return _join(words)


def prefix(label: str | None) -> str:
    """MATH-4 display-line prefix: "equation 3: " for a numbered display, else ""."""
    return f"equation {label}: " if label else ""
