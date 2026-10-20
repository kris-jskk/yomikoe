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

import re

from hearnarro.ingestion.mathspeak import symbols as sy
from hearnarro.ingestion.mathspeak.structure import (
    LIMOPS,
    RELATIONS,
    MathSpan,
    Node,
    cmex_text,
    label_of,
)

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


def _opens_with_word(group: Node) -> bool:
    inner = group.children[0] if group.children else None
    first = inner.children[0] if inner is not None and inner.children else None
    return first is not None and first.kind == "word"


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
            if it.kind == "op" and it.text == "#":
                words.append("number of")  # "# of x" / "#x": the number of x (§3c, 2026-10-17)
                after = items[i + 1] if i + 1 < len(items) else None
                if after is not None and after.kind == "name" and after.text == "of":
                    prev, i = after, i + 2
                    continue
                if [n.text for n in items[i + 1 : i + 3] if n.kind == "var"] == ["o", "f"]:
                    prev, i = items[i + 2], i + 3  # "# of x" with "of" lexed as two letters
                    continue
            elif it.kind == "op":
                words.append(self.op(it.text, items[i + 1 :], colon_seen, limit, setbuilder))
                colon_seen = colon_seen or it.text == ":"
            else:
                if (
                    it.kind in ("group", "abs")
                    and prev is not None
                    and (
                        prev.kind in ("num", "group")
                        or (prev.kind == "var" and _opens_with_word(it))
                    )
                ):
                    words.append("times")  # 2(k - 1): a parenthesized factor, not an argument
                words.extend(self.item(it, limit=limit))
            prev, i = it, i + 1
        return words

    def op(
        self, sym: str, rest: list[Node], colon_seen: bool, limit: bool, setbuilder: bool
    ) -> str:
        if not sym:
            return ""
        if sym in _ATTACH:
            return sym
        if sym == ".":
            return ""
        if sym == ":":
            ahead: list[Node] = []
            for n in rest:  # up to the next condition mark
                if n.kind == "op" and n.text in (":", "|"):
                    break
                ahead.append(n)
            maps = any(n.kind == "op" and n.text in ("→", "↦") for n in ahead)
            return "from" if maps else "such that"
        if sym == "→":
            return "to" if colon_seen else "approaches"
        if sym == "|":
            return "such that" if setbuilder else "given"
        if len(sym) > 1 and sym not in sy.SYMBOLS:
            return _join([sy.name_of(c) or "" for c in sym if not c.isspace()])
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
        if k == "name":
            return [n.text]
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
            if kids[0] is not None and kids[0].kind == "group" and kids[0].text in ("()", "{}"):
                return self.family(kids[0], kids[1], None)
            return [*self.item(kids[0], limit=limit), "sub", *self.script(kids[1])]  # type: ignore[arg-type]
        if k == "prime":
            return [*self.item(kids[0]), "double prime" if n.text == "″" else "prime"]  # type: ignore[arg-type]
        if k == "accent":
            base = self.item(kids[0])  # type: ignore[arg-type]
            return ["vector", *base] if n.text == "vector" else [*base, n.text]
        if k == "frac":
            num, den = self.row(kids[0], limit=limit), self.row(kids[1], limit=limit)
            if (_flat(kids[0]), _flat(kids[1])) in _NUMERIC_FRACTIONS:
                return [_NUMERIC_FRACTIONS[(_flat(kids[0]), _flat(kids[1]))]]
            if all(
                len(c.children) == 1 and c.children[0] and not c.children[0].children
                for c in kids
                if c is not None
            ):
                return [*num, "over", *den]
            return ["the fraction", *num, "over", *den, ",", "end fraction"]
        if k == "sqrt":
            kid = kids[0]
            if kid is not None and kid.kind == "group" and kid.text == "()" and kid.children[0]:
                kid = kid.children[0]  # √(…): the brackets only delimit the radicand (m5-p3j)
            return ["the square root of", *self.item(kid)]  # type: ignore[arg-type]
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
        if k == "opnorm":
            return ["the operator norm of", *self.row(kids[0])]
        if k == "colvec":  # spec §3c: "the column vector a, b" (m5 p3n)
            words = ["the column vector"]
            for r, row in enumerate(c for c in kids if c is not None):
                if r:
                    words.append(",")
                words.extend(self.row(row))
            return words
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

    def family(self, group: Node, lo: Node | None, hi: Node | None) -> list[str]:
        """An indexed family, ``(X_t)_{t≥0}`` "x sub t for t greater than or equal to 0" and
        ``{(x_i, y_i)}_{i=1}^n`` "the set of x sub i, y sub i for i equals 1 to n" (§3c)."""
        inner = self.row(group.children[0])
        words = ["the set of", *inner] if group.text == "{}" else inner
        if lo is not None:
            words += ["for", *self.row(lo, limit=True)]
        if hi is not None:
            words += ["to", *self.script(hi)]
        return words

    def script(self, row: Node | None) -> list[str]:
        if row is not None and any(c is not None and c.kind == "name" for c in row.children):
            return self.row(row, limit=True)
        flat = _flat(row)
        if len(flat) >= 3 and flat.isascii() and flat.isalpha() and flat.islower():
            return [flat]  # x_{emp}: a word or abbreviation is read as a word
        return self.row(row, limit=True)

    def sup(self, base: Node | None, script: Node | None, limit: bool) -> list[str]:
        if (
            base is not None
            and base.kind == "sub"
            and base.children[0] is not None
            and base.children[0].kind == "group"
            and base.children[0].text in ("()", "{}")
        ):
            return self.family(base.children[0], base.children[1], script)
        words = self.item(base, limit=limit) if base is not None else []
        if base is not None and base.kind in (
            "group",
            "apply",
            "abs",
            "norm",
            "opnorm",
            "interval",
            "sub",
        ):
            words.append(",")  # a comma closes a group (or a subscript) before a power
        flat = _flat(script)
        kids = [c for c in (script.children if script else []) if c is not None]
        if len(kids) > 1 and kids[0].kind in ("op", "prime") and kids[0].text in ("′", "″"):
            # s^{′⊤}: primes set in the exponent come first, "s prime transpose"
            mark = "double prime" if kids[0].text == "″" else "prime"
            return [*words, mark, *self.sup(None, Node("row", list(kids[1:])), limit)]
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
        if any(c.kind == "name" for c in kids):
            return [*words, "sup", *self.row(script, limit=True)]
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
    """MATH-1: "equation N" (or "equation") then every symbol left to right by name; never empty.

    An inline span (``display`` False) is read without the "equation" word: it sits inside a
    sentence. A digit run (with decimal points) is one number and a function name (``log``,
    ``tr``, ``max``) one word, so neither is spelled out character by character."""
    raw = text if text is not None else _span_text(span)
    label = (span.label or label_of(raw)) if span.display else None
    if not span.display:
        words: list[str] = []
    else:
        words = ["equation", label] if label else ["equation"]
    if label:
        head = _LABEL_HEAD_RE.match(raw)
        if head and head.group(1) == label:
            raw = raw[head.end() :]
        elif "(" in raw:
            raw = raw[: raw.rfind("(")]
    for tok in _FALLBACK_TOKEN.findall(cmex_text(raw)):
        if tok[0].isdigit():
            words.append(tok)
        elif len(tok) > 1 and (tok in sy.FUNCTIONS or tok in LIMOPS):
            words.append(sy.FUNCTIONS.get(tok, tok))
        else:
            for ch in tok:
                name = sy.name_of(ch) or sy.ACCENTS.get(ch)
                if name:
                    words.append(name)
    if not words:
        words = ["equation"]
    return _join(words)


_LABEL_HEAD_RE = re.compile(r"^\s*\(\s*(\d+(?:\.\d+)*)\s*\)\s+")
_FALLBACK_TOKEN = re.compile(r"\d+(?:\.\d+)*|[A-Za-z]+|\S")


def prefix(label: str | None) -> str:
    """MATH-4 display-line prefix: "equation 3: " for a numbered display, else ""."""
    return f"equation {label}: " if label else ""
