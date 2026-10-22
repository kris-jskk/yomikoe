"""Stage 4: merge lines and cross-page blocks (ING-5)."""

from __future__ import annotations

import re
from dataclasses import replace

from yomikoe.ingestion.classify import (
    BOILERPLATE_RE,
    EMAIL,
    MATH_CHARS,
    SCRIPT_RATIO,
    _is_math_font,
)
from yomikoe.ingestion.models import (
    BULLET_GLYPHS,
    INLINE_ITEM_RE,
    ITEM_RE,
    Block,
    Line,
    LogicalBlock,
    MathSpan,
    Span,
)
from yomikoe.ingestion.segment import _segmenter

TERMINAL_PUNCT = '.!?:;"”’'
# Non-body types that end a join candidate: a new section, a list or a display equation
# interrupts the sentence. Other non-body types (footnote, caption, table, ...) are floats.
JOIN_BLOCKERS = {"heading", "list", "equation"}
# MATH-2: block types whose maths-font runs become inline MathSpans (a list item's text is
# rebuilt by split_items, so lists carry none yet).
INLINE_MATH_TYPES = {"body", "heading", "caption", "footnote"}
# ... and the types whose text-font maths is found by content (``content_spans``), lists included.
CONTENT_MATH_TYPES = INLINE_MATH_TYPES | {"list"}
PARA_JOIN_GAP = 1.0  # same-page join: B starts at most this many of A's font sizes below A
# ... and the join is on only for documents where stage 1 split paragraphs systematically:
# at least PARA_JOIN_MIN_COUNT candidate pairs making up PARA_JOIN_MIN_SHARE of the body
# blocks (the user book: 350 pairs, 0.23; golden fixtures at most 8 pairs, 0.13; results 195).
PARA_JOIN_MIN_COUNT = 10
PARA_JOIN_MIN_SHARE = 0.15
FLOAT_SIZE_RATIO = 0.85  # body text this much smaller than the open paragraph is a label
EMAIL_TOKEN_RE = re.compile(
    r"\{[^}]*\}\s*@[\w-]+(?:\.[\w-]+)+|[\w.+-]+(?:,\s?[\w.+-]+)*@[\w-]+(?:\.[\w-]+)+"
)
ABSTRACT_RE = re.compile(r"^\s*abstract\b", re.IGNORECASE)
EMAIL_ONLY_RE = re.compile(rf"^{EMAIL}(?:[\s,;]+{EMAIL})*[\s,;.]*$")


# Visible hyphens a line may end with: ASCII hyphen-minus, U+2010 HYPHEN, U+2011 NON-BREAKING
# HYPHEN. All follow one rule: dropped before a lowercase continuation, kept otherwise.
LINE_END_HYPHENS = ("-", "\u2010", "\u2011")
SOFT_HYPHEN = "\u00ad"  # invisible break point: always dropped at a line end, no space added


def merge_lines(lines: list[str], *, heading: bool = False) -> str:
    """Join lines with spaces, de-hyphenating before a lowercase continuation.

    A soft hyphen ending a line is removed and the next line joined without a space. A soft
    hyphen ending the last line is left in place so a later cross-block ``merge_lines`` call
    can still join on it; ``merge_blocks`` strips any that remain. In a heading (``heading``),
    a line ending in a hyphen before any other continuation keeps the hyphen and joins with
    no space ("Multi-" + "Modal" -> "Multi-Modal", ING-4 document 17).
    """
    return merge_lines_map(lines, heading=heading)[0]


def _collapse(line: str) -> tuple[str, list[int]]:
    """``" ".join(line.split())`` and, per character of ``line``, its index in the result
    (-1 for whitespace that was dropped)."""
    out: list[str] = []
    pos: list[int] = []
    pending = False
    for ch in line:
        if ch.isspace():
            if out and not pending:
                pending = True
                pos.append(len(out))  # the run's first space becomes the single space
            else:
                pos.append(-1)
            continue
        if pending:
            out.append(" ")
            pending = False
        pos.append(len(out))
        out.append(ch)
    if pending:  # trailing whitespace: the space it would have become is dropped
        for k in range(len(pos) - 1, -1, -1):
            if pos[k] == len(out):
                pos[k] = -1
                break
    return "".join(out), pos


def merge_lines_map(lines: list[str], *, heading: bool = False) -> tuple[str, list[list[int]]]:
    """``merge_lines`` plus, for every character of every input line, its index in the merged
    text (-1 when dropped: collapsed whitespace, a line-end hyphen joined away). MATH-2 uses it
    to place maths runs of a line inside the merged block text (spec m5 §3a)."""
    out = ""
    maps: list[list[int]] = []
    last: tuple[int, int] | None = None  # (line, char) owning out's last character
    for li, line in enumerate(lines):
        part, pos = _collapse(line)
        if not part:
            maps.append([-1] * len(line))
            continue
        if out.endswith(SOFT_HYPHEN) or (out.endswith(LINE_END_HYPHENS) and part[0].islower()):
            if last is not None:
                maps[last[0]][last[1]] = -1
            out = out[:-1]
            offset = len(out)
        elif heading and out.endswith(LINE_END_HYPHENS):
            offset = len(out)
        elif out:
            out = out + " "
            offset = len(out)
        else:
            offset = 0
        out = out + part
        maps.append([p + offset if p >= 0 else -1 for p in pos])
        last = (li, max(k for k, p in enumerate(pos) if p >= 0))
    return out, maps


_GLYPHS = frozenset(BULLET_GLYPHS)


def split_items(lines: list[str]) -> list[str]:
    """A list block's items (ING-5): each item line (``ITEM_RE``) plus the continuation
    lines after it, joined by ``merge_lines``. A line holding several glyph items
    ("→ a → b") is split before each glyph preceded by whitespace; a glyph alone on its
    line takes the next line as its text."""
    items: list[list[str]] = []
    for line in lines:
        for k, piece in enumerate(INLINE_ITEM_RE.split(line)):
            if not piece.strip():
                continue
            glyph_only = bool(items) and len(items[-1]) == 1 and items[-1][0].strip() in _GLYPHS
            if items and (glyph_only or (k == 0 and not ITEM_RE.match(piece))):
                items[-1].append(piece)
            else:
                items.append([piece])
    return [text for text in (merge_lines(item) for item in items) if text]


def _item_lines(lines: list[str]) -> list[list[int]] | None:
    """The line indices of each ``split_items`` item when every item is made of whole lines
    (no line split before an inline glyph, no glyph-only line), else None: only then can an
    item's inline maths runs be found on its own lines (``_inline_spans``)."""
    groups: list[list[int]] = []
    for k, line in enumerate(lines):
        pieces = [p for p in INLINE_ITEM_RE.split(line) if p.strip()]
        if not pieces:
            continue
        if len(pieces) != 1 or pieces[0] != line or line.strip() in _GLYPHS:
            return None
        if groups and not ITEM_RE.match(line):
            groups[-1].append(k)
        else:
            groups.append([k])
    if [merge_lines([lines[k] for k in g]) for g in groups] != split_items(lines):
        return None
    return groups


# ING-7: cells of a table row are spans this many font sizes apart; closer spans are one cell.
CELL_GAP = 1.0
WORD_GAP = 0.15  # spans of one cell further apart than this (in font sizes) get a space
EQUATION_LABEL_RE = re.compile(r"\((\d{1,3}[a-z]?)\)\s*$")


def table_cells(line: Line) -> list[str]:
    """The cells of one table row (ING-7): its spans left to right, split where the gap to the
    previous span exceeds CELL_GAP font sizes."""
    cells: list[str] = []
    prev: Span | None = None
    for span in sorted(line.spans, key=lambda sp: sp.bbox.x0):
        text = " ".join(span.text.split())
        if not text:
            continue
        size = max(span.size, prev.size if prev else 0.0, 1.0)
        gap = span.bbox.x0 - prev.bbox.x1 if prev is not None else 0.0
        if prev is None or gap > CELL_GAP * size:
            cells.append(text)
        else:
            cells[-1] += (" " if gap > WORD_GAP * size else "") + text
        prev = span
    return cells


def table_rows(block: Block) -> list[str]:
    """Spoken rows of a table block (ING-7): cells joined with ", ", ended with "."; a row with
    no alphabetic character is skipped."""
    rows: list[str] = []
    for line in block.lines:
        if is_noise_line(line.text):
            continue
        row = ", ".join(table_cells(line)).rstrip(" .,;:")
        if any(c.isalpha() for c in row):
            rows.append(row + ".")
    return rows


def code_cue(code: str) -> str:
    """ "Code listing, N lines." with N the non-empty lines of ``code`` (ING-10)."""
    n = sum(1 for line in code.split("\n") if line.strip())
    return f"Code listing, {n} {'line' if n == 1 else 'lines'}."


def equation_label(raw_lines: list[str]) -> str | None:
    """The label of a display equation, "3" from a line ending in "(3)" (MATH-4)."""
    for line in raw_lines:
        m = EQUATION_LABEL_RE.search(line)
        if m:
            return m.group(1)
    return None


def equation_cue(raw_lines: list[str]) -> str:
    """ "Equation N." when a label like "(3)" ends a line of the block, else "Equation." (ING-7)."""
    for line in raw_lines:
        m = EQUATION_LABEL_RE.search(line)
        if m:
            return f"Equation {m.group(1)}."
    return "Equation."


def _table_groups(blocks: list[Block]) -> dict[int, tuple[int, int]]:
    """Index of the first block of each run of consecutive same-page table blocks -> (table
    number, spoken rows in the run). Tables are numbered through the document (ING-7)."""
    groups: dict[int, tuple[int, int]] = {}
    number = 0
    first: int | None = None
    for i, block in enumerate(blocks):
        if block.type != "table" or block.inline:
            first = None
            continue
        rows = len(table_rows(block))
        if first is not None and blocks[i - 1].page == block.page:
            n, r = groups[first]
            groups[first] = (n, r + rows)
            continue
        number += 1
        first = i
        groups[i] = (number, rows)
    return groups


def _math_runs(line: Line) -> list[list[int]]:
    """Indices of the spans of ``line`` forming inline maths runs (MATH-2): maximal runs of
    maths-font spans, extended over the scripts next to them (superscript, or smaller than
    SCRIPT_RATIO of the line's largest size) and whitespace-only spans between them."""
    top = max((s.size for s in line.spans), default=0.0)

    def mathy(s: Span) -> bool:
        return bool(s.text.strip()) and _is_math_font(s.font)

    variables = _italic_variables(line)

    def script(s: Span) -> bool:
        return bool(s.text.strip()) and (s.superscript or s.size < SCRIPT_RATIO * top)

    runs: list[list[int]] = []
    cur: list[int] = []
    for k, s in enumerate(line.spans):
        if mathy(s) or k in variables or (cur and (script(s) or not s.text.strip())):
            cur.append(k)
        else:
            if cur:
                runs.append(cur)
            cur = []
            # a script directly before a maths span opens the run with it
            if script(s) and k + 1 < len(line.spans) and mathy(line.spans[k + 1]):
                cur = [k]
    if cur:
        runs.append(cur)
    out: list[list[int]] = []
    for run in runs:
        while run and not line.spans[run[-1]].text.strip():
            run.pop()
        if any(mathy(line.spans[k]) or k in variables for k in run):
            out.append(run)
    return out


# MATH-2 (m5 p3i): a variable set in the text face's italic (or a calligraphic slant) inside
# upright prose ("the denominator is *N*", "the symbol *s*²", "let *F* be a class") is maths
# though no maths font is used. Only a lone letter counts, with no italic span next to it (an
# italic phrase is emphasis, not a variable), in a line that holds upright prose words.
_SLANT_FONT_RE = re.compile(r"Italic|Oblique|Slant|Calligraphic", re.IGNORECASE)
_PROSE_WORD_RE = re.compile(r"[A-Za-z]{3}")
_SPACING_ACCENTS = frozenset("¯ˆ˜˙¨ˇ")


def _variable_span(sp: MathSpan) -> bool:
    """An inline span made by ``_italic_variables`` alone: no run in a maths font, and one
    slanted letter (its scripts aside)."""
    if not sp.runs or sp.display or any(_is_math_font(r.font) for r in sp.runs):
        return False
    base = [r for r in sp.runs if r.text.strip() and not r.superscript]
    return len(base) == 1 and _slanted(base[0]) and len(base[0].text.strip().strip(_EDGE)) == 1


def _slanted(s: Span) -> bool:
    return s.italic or bool(_SLANT_FONT_RE.search(s.font))


def _italic_variables(line: Line) -> set[int]:
    """Indices of the spans of ``line`` that are a lone italic letter in upright prose."""
    spans = line.spans
    if not any(
        not _slanted(s) and not _is_math_font(s.font) and _PROSE_WORD_RE.search(s.text)
        for s in spans
    ):
        return set()
    out: set[int] = set()
    for k, s in enumerate(spans):
        core = s.text.strip().strip(_EDGE)
        if len(core) != 1 or not core.isalpha() or not _slanted(s) or _is_math_font(s.font):
            continue
        near = [spans[j] for j in (k - 1, k + 1) if 0 <= j < len(spans)]
        if any(_slanted(n) and n.text.strip() and not n.superscript for n in near):
            continue
        out.add(k)
        if k + 1 < len(spans) and spans[k + 1].text.strip() in _SPACING_ACCENTS:
            out.add(k + 1)  # "x" then "¯" set as its own glyph: x bar
    return out


# MATH-2 (m5 p3d): maths set in a text font (textbook pages, OCR text) has no maths-font run,
# so it is found by content. A relation token is maths wherever it stands; an operation token is
# maths next to an operand; a dash is a minus only after a symbolic operand ("x – mean",
# "n − 1"), never after a word. The span widens over the operands next to it (a letter, a
# number, a token holding a MATH_CHARS glyph or brackets); a span never holds a word of three
# letters, so prose words stay with the prose reader.
CONTENT_RELATIONS = frozenset("=<>≤≥~∼≈≠±≡∝∈")
CONTENT_OPERATIONS = frozenset("+×÷·→⋅∗")
CONTENT_DASHES = frozenset("-–−")
_TOKEN_RE = re.compile(r"\S+")
_NUMBER_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
BRACKET_REACH = 4
_EDGE = ".,;:!?\"'“”‘’"
_SYMBOLIC_RE = re.compile(r"^[\w¯′'#.*/^()\[\]{}+\-–−,|=<>~]+$")
_WORD3_RE = re.compile(r"[A-Za-z]{3}")
# MATH-2 (m5 p3h): a function name from this short list, directly followed by "(" or a script
# ("exp(-1/x)", "log_2", "max^"), is maths, not a prose word; scientific notation ("1e-8",
# "2.5E+3", "10^-8", "10−8" with a true minus from a lost superscript) is a number in maths.
FUNCTION_NAMES = ("exp", "log", "ln", "sin", "cos", "tan", "min", "max", "arg", "lim", "det")
FUNCTION_NAMES += ("tr", "sup", "inf")
_FUNCTION_RE = re.compile(rf"(?<![A-Za-z])(?:{'|'.join(FUNCTION_NAMES)})(?=[(_^])")
_SCIENTIFIC_RE = re.compile(r"^[-−]?\d+(?:\.\d+)?[eE][-+−]?\d+$|^[-−]?10(?:\^[-+−]?|−)\d+$")
_INNER_RELATION_RE = re.compile(r"[=<>≤≥]")
_GLYPHS_NONASCII = frozenset(c for c in MATH_CHARS if not c.isascii())


def _has_word(text: str) -> bool:
    """A prose word of three letters or more, function names before "(" or a script aside."""
    return bool(_WORD3_RE.search(_FUNCTION_RE.sub("", text)))


def _core(tok: str) -> str:
    return tok.strip(_EDGE)


def _glyph_token(core: str) -> bool:
    return any(c in _GLYPHS_NONASCII or "Ͱ" <= c <= "Ͽ" or c == "√" for c in core)


def _operand(tok: str) -> bool:
    """A symbolic operand: a letter, a number, a glyph token, a bracket group; no word."""
    core = _core(tok)
    if not core or core in CONTENT_RELATIONS | CONTENT_OPERATIONS | CONTENT_DASHES:
        return False
    if _glyph_token(core):
        return True
    return bool(_SYMBOLIC_RE.match(core)) and not _has_word(core) and core != "a"


def _inner_relation(tok: str) -> bool:
    """A token like "x=17" or "Z=" (OCR): a relation sign inside a short non-link token."""
    core = _core(tok)
    return (
        0 < len(core) <= 15
        and bool(_INNER_RELATION_RE.search(core))
        and "://" not in core
        and "@" not in core
        and not core.startswith(("<", ">"))
    )


def content_spans(text: str, taken: list[MathSpan] | None = None) -> list[MathSpan]:
    """Inline MathSpans (no runs) over text-font maths in ``text`` by content (MATH-2): see
    CONTENT_RELATIONS. Spans overlapping ``taken`` are dropped. Pure."""
    toks = [(m.start(), m.end(), m.group()) for m in _TOKEN_RE.finditer(text)]
    marks: list[tuple[int, int]] = []  # token index ranges [lo, hi]
    for i, (_, _, tok) in enumerate(toks):
        core = _core(tok)
        left = i > 0 and _operand(toks[i - 1][2])
        right = i + 1 < len(toks) and _operand(toks[i + 1][2])
        if core in CONTENT_RELATIONS or (core in CONTENT_OPERATIONS and (left or right)):
            marks.append((i - 1 if left else i, i + 1 if right else i))
        elif core in CONTENT_DASHES and left and i + 1 < len(toks):
            numbers = _NUMBER_RE.match(_core(toks[i - 1][2])) and _NUMBER_RE.match(
                _core(toks[i + 1][2])
            )
            if core == "−" or not numbers:  # "2015 – 2020" is a range, "5 − 2" a minus
                marks.append((i - 1, i + 1 if right else i))
        elif _inner_relation(tok):  # a lone glyph token is the reader's (glyph_spans, units)
            marks.append((i, i))
        elif _SCIENTIFIC_RE.match(core) or (_FUNCTION_RE.match(core) and "(" in core):
            marks.append((i, i))  # "1e-8", "10^-8", "exp(-x)": maths standing alone (p3h)
    merged: list[list[int]] = []
    for lo, hi in sorted(marks):
        if merged and (lo <= merged[-1][1] or (lo == merged[-1][1] + 1 and _operand(toks[lo][2]))):
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    for m in merged:  # an open bracket group ("N(5, 6)") closes within BRACKET_REACH tokens
        depth = sum(t[2].count("(") - t[2].count(")") for t in toks[m[0] : m[1] + 1])
        reach = 0
        while (
            depth > 0
            and m[1] + 1 < len(toks)
            and reach < BRACKET_REACH
            and not _has_word(toks[m[1] + 1][2])
        ):
            m[1] += 1
            reach += 1
            depth += toks[m[1]][2].count("(") - toks[m[1]][2].count(")")
    busy = [(sp.start, sp.end) for sp in taken or []]
    out: list[MathSpan] = []
    for lo, hi in merged:
        s, e = toks[lo][0], toks[hi][1]
        while s < e and text[s] in _EDGE + "([":
            if text[s] in "([" and text[s:e].count(text[s]) <= text[s:e].count(
                ")]"["([".index(text[s])]
            ):
                break
            s += 1
        while e > s and text[e - 1] in _EDGE + ")]":
            if text[e - 1] in ")]" and text[s:e].count(text[e - 1]) <= text[s:e].count(
                "(["[")]".index(text[e - 1])]
            ):
                break
            e -= 1
        if s < e and not _has_word(text[s:e]) and not any(s < b and a < e for a, b in busy):
            out.append(MathSpan(s, e, False, []))
    return out


def _inline_spans(lines: list[Line], texts: list[str], heading: bool) -> list[MathSpan]:
    """Inline MathSpans over the maths-font runs of ``lines`` in ``merge_lines(texts)``.
    A line whose kept text differs from its spans' text (email stripping) gets none."""
    _, maps = merge_lines_map(texts, heading=heading)
    spans: list[MathSpan] = []
    for line, text, pos in zip(lines, texts, maps, strict=True):
        if text != line.text:
            continue
        starts: list[int] = []
        acc = 0
        for s in line.spans:
            starts.append(acc)
            acc += len(s.text)
        for run in _math_runs(line):
            lo = starts[run[0]]
            k = run[0] - 1
            if k >= 0 and line.spans[k].text[-1:] in _SPACING_ACCENTS:
                # unicode-math sets \dot{y} as "˙" ending the text run before "𝑦": the accent
                # opens the maths span, read "y dot" (MATH-2, m5 p3n)
                lo -= 1
                run = [k, *run]
            last = line.spans[run[-1]].text
            hi = starts[run[-1]] + len(last)
            if not any(_is_math_font(line.spans[k].font) for k in run):
                hi -= len(last) - len(last.rstrip())  # an italic variable ends at its letter
            kept = [p for p in pos[lo:hi] if p >= 0]
            if kept:
                runs = [line.spans[k] for k in run]
                if runs[0].text[-1:] in _SPACING_ACCENTS and len(runs[0].text) > 1:
                    runs[0] = replace(runs[0], text=runs[0].text[-1])
                if not any(_is_math_font(r.font) for r in runs) and any(
                    r.text.strip() in _SPACING_ACCENTS for r in runs
                ):
                    runs = []  # an accented italic variable is read from its text ("x¯")
                spans.append(MathSpan(kept[0], kept[-1] + 1, False, runs))
    return spans


def _shift(spans: list[MathSpan], lo: int, hi: int, offset: int) -> list[MathSpan]:
    """Spans starting in [lo, hi), clipped to hi and moved by ``offset``."""
    out: list[MathSpan] = []
    for s in spans:
        if lo <= s.start < hi:
            end = min(s.end, hi)
            if end > s.start:
                out.append(MathSpan(s.start + offset, end + offset, s.display, s.runs, s.label))
    return out


def _join(target: LogicalBlock, text: str, spans: list[MathSpan]) -> None:
    """``target.text = merge_lines([target.text, text])``, keeping both sides' MathSpans.

    Both texts are already merged (single spaces), so the head keeps its offsets (less a
    line-end hyphen joined away) and ``text`` lands at the end of the joined text."""
    joined = merge_lines([target.text, text])
    tail = " ".join(text.split())
    head_len = len(joined) - len(tail)
    kept = _shift(target.math_spans, 0, head_len, 0)
    if tail == text:
        kept.extend(_shift(spans, 0, len(text), head_len))
    target.text = joined
    target.math_spans = kept


def is_noise_line(text: str) -> bool:
    """A line never read even inside a kept block: email-only, or BOILERPLATE_RE."""
    line = " ".join(text.split())
    return bool(EMAIL_ONLY_RE.match(line) or BOILERPLATE_RE.match(line))


def strip_emails(text: str) -> str:
    """Remove email tokens (incl. "{a, b}@host" and "a,b@host" lists) and dangling separators."""
    out = EMAIL_TOKEN_RE.sub("", text)
    if out == text:
        return text
    return re.sub(r"[\s,;]+$", "", re.sub(r"\s{2,}", " ", out)).strip()


def _continues(prev_text: str, next_text: str, page_break: bool) -> bool:
    """B continues A: B starts lowercase, or (page break only) A lacks terminal punctuation."""
    prev = prev_text.rstrip()
    nxt = next_text.lstrip()
    if not prev or not nxt:
        return False
    return nxt[0].islower() or (page_break and prev[-1] not in TERMINAL_PUNCT)


PARA_TERMINAL = TERMINAL_PUNCT + ")"
OPENERS = "([{“‘\"'"


def _starts_lower(text: str) -> bool:
    """Starts with a lowercase letter, or an opening bracket/quote then a lowercase letter."""
    if text[:1].islower():
        return True
    return len(text) > 1 and text[0] in OPENERS and text[1].islower()


def _continues_paragraph(prev_text: str, next_text: str) -> bool:
    """Same page, no flow break: stage 1 split a paragraph (found on a user book whose
    justified lines start 0.5-2 pt apart, which UNTAGGED_INDENT_MAX reads as new blocks).
    A ends with a line-end hyphen, or without terminal punctuation, and B starts lowercase."""
    prev = prev_text.rstrip()
    nxt = next_text.lstrip()
    if not prev or not nxt or not _starts_lower(nxt):
        return False
    return prev.endswith((*LINE_END_HYPHENS, SOFT_HYPHEN)) or prev[-1] not in PARA_TERMINAL


def _same_page_pair(prev: Block, prev_text: str, block: Block, text: str) -> bool:
    """B sits directly under body block A on the same page and continues its paragraph."""
    return (
        block.page == prev.page
        and not _is_flow_break(prev, block)
        and block.bbox.y0 - prev.bbox.y1 <= PARA_JOIN_GAP * _size(prev)
        and _continues_paragraph(prev_text, text)
    )


def _paragraph_joins_on(blocks: list[Block]) -> bool:
    """Stage 1 split paragraphs systematically in this document (PARA_JOIN_MIN_*)."""
    body = [b for b in blocks if b.type == "body" and not b.inline]
    texts = [merge_lines([ln.text for ln in b.lines]) for b in body]
    pairs = sum(
        1
        for i in range(1, len(body))
        if _same_page_pair(body[i - 1], texts[i - 1], body[i], texts[i])
    )
    return pairs >= PARA_JOIN_MIN_COUNT and pairs >= PARA_JOIN_MIN_SHARE * len(body)


def _first_sentence(text: str) -> tuple[str, str]:
    """Split ``text`` after its first sentence (pysbd, as stage 5 will split it)."""
    spans = _segmenter().segment(text)
    if len(spans) < 2:
        return text, ""
    cut = spans[1].start
    return text[:cut].rstrip(), text[cut:].lstrip()


def _is_flow_break(prev: Block, block: Block) -> bool:
    """True when ``block`` starts a new page or a new column (it starts above ``prev``)."""
    return block.page != prev.page or block.bbox.y0 < prev.bbox.y0


def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]:
    """One LogicalBlock per Block, joining body text that continues across a flow break.

    A flow break is a page break or a column break (the next body block starts above the
    previous one). Body block B joins the last body block A when only floats (caption,
    table, footnote, image, and body or heading text in a font smaller than
    FLOAT_SIZE_RATIO x A's, i.e. figure labels) lie between them, never a heading, list or equation, and
    B starts lowercase, or B is on the next page and A lacks terminal punctuation. Without a
    flow break, body block B joins the body block A directly before it on the same page when
    B starts within PARA_JOIN_GAP font sizes below A and ``_continues_paragraph`` holds
    (stage 1 split a paragraph), in documents where that happens systematically
    (``_paragraph_joins_on``). When
    floats lie between A and B only B's first sentence moves up into A; the rest of B stays
    after the floats. A list block becomes one LogicalBlock per item (``split_items``).
    Email-only and boilerplate lines (``is_noise_line``) are dropped, and
    on page 0 before the "Abstract" heading (the author block) email tokens are stripped
    from every line ("AI Singapore, Singapore a,b@x.org" -> "AI Singapore, Singapore").
    """
    in_author_block = True
    paragraph_joins = _paragraph_joins_on(blocks)
    tables = _table_groups(blocks)
    out: list[LogicalBlock] = []
    candidate: int | None = None  # index in ``out`` of the last body block seen
    last_body: Block | None = None
    for i, block in enumerate(blocks):
        kept = [ln for ln in block.lines if not is_noise_line(ln.text)]
        lines = [ln.text for ln in kept]
        if block.page > 0 or ABSTRACT_RE.match(block.text):
            in_author_block = False
        if in_author_block and block.type in ("heading", "body"):
            lines = [strip_emails(ln) for ln in lines]
        heading = block.type == "heading"
        text = merge_lines(lines, heading=heading)
        spans = _inline_spans(kept, lines, heading) if block.type in INLINE_MATH_TYPES else []
        if block.inline and out and text:
            # Stage 3 found this block continuing the previous block's text line (inline maths).
            host = out[-1]
            runs = [sp for ln in kept for sp in ln.spans if sp.text.strip()]
            if host.type == "code" and host.raw_text is not None:
                host.raw_text = host.raw_text + "\n" + "\n".join(lines)
                host.text = code_cue(host.raw_text)
            elif host.type == "table":
                host.text = merge_lines([host.text, text])
            elif host.type == "equation" and host.math_spans:
                # MATH-1: a fragment continuing a display equation widens its one span
                _join(host, text, [])
                display = host.math_spans[0] if host.math_spans else None
                if display is not None:
                    display.end = len(host.text)
                    display.runs = [*display.runs, *runs]
                host.raw_text = host.text
            else:
                # MATH-2: the characters the fragment added are one inline span
                _join(host, text, [MathSpan(0, len(text), False, runs)])
            host.source.append((block.page, block.index))
            continue
        if (
            block.type in ("body", "heading")
            and last_body is not None
            and candidate is not None
            and _size(block) < FLOAT_SIZE_RATIO * _size(last_body)
        ):
            # Small-print body or heading text (figure labels) between fragments is a float.
            out.append(_logical(len(out), block, text, spans=spans))
            continue
        if block.type == "body":
            if (
                candidate is not None
                and last_body is not None
                and (
                    (
                        block.page in (last_body.page, last_body.page + 1)
                        and _is_flow_break(last_body, block)
                        and _continues(out[candidate].text, text, block.page != last_body.page)
                    )
                    or (
                        paragraph_joins
                        and candidate == len(out) - 1
                        and _same_page_pair(last_body, out[candidate].text, block, text)
                    )
                )
            ):
                target = out[candidate]
                head, rest = (text, "") if candidate == len(out) - 1 else _first_sentence(text)
                rest_at = len(text) - len(rest)
                _join(target, head, _shift(spans, 0, len(head), 0))
                target.source.append((block.page, block.index))
                if rest:
                    rest_spans = _shift(spans, rest_at, len(text), -rest_at)
                    out.append(_logical(len(out), block, rest, spans=rest_spans))
                    candidate = len(out) - 1
            else:
                out.append(_logical(len(out), block, text, spans=spans))
                candidate = len(out) - 1
            last_body = block
            continue
        if block.type in JOIN_BLOCKERS:
            candidate = None
        if block.type == "table":
            # ING-7: a cue "Table N, R rows." on the first block of a table, then one line per
            # spoken row; split_sentences makes one segment per line.
            spoken = table_rows(block)
            if i in tables:
                number, rows = tables[i]
                if rows:
                    spoken.insert(0, f"Table {number}, {rows} {'row' if rows == 1 else 'rows'}.")
            out.append(_logical(len(out), block, "\n".join(spoken), raw=text))
            continue
        if block.type == "equation":
            # MATH-1: the raw expression is the text and one display span covers it; the
            # mathspeak reader speaks it (its fallback is the ING-7 cue). raw_text keeps the
            # same text for the D14 excluded-mass guard.
            runs = [sp for ln in kept for sp in ln.spans if sp.text.strip()]
            display = [MathSpan(0, len(text), True, runs, equation_label(lines))] if text else []
            out.append(_logical(len(out), block, text, raw=text, spans=display))
            continue
        if block.type == "code":
            # ING-10: one cue "Code listing, N lines."; raw_text keeps the code (VIEW-1, D14).
            # Consecutive code blocks on one page are one listing.
            code = "\n".join(ln for ln in lines if ln.strip())
            if not code:
                continue
            prev = blocks[i - 1] if i else None
            if (
                out
                and out[-1].type == "code"
                and out[-1].raw_text is not None
                and prev is not None
                and prev.type == "code"
                and prev.page == block.page
            ):
                listing = out[-1]
                listing.raw_text = f"{listing.raw_text}\n{code}"
                listing.source.append((block.page, block.index))
            else:
                listing = _logical(len(out), block, "", raw=code)
                out.append(listing)
            listing.text = code_cue(listing.raw_text or "")
            continue
        if block.type == "list":
            groups = _item_lines(lines)
            for item in split_items(lines):
                # MATH-2 (m5 p3k): an item made of whole lines keeps its maths-font runs
                rows = groups.pop(0) if groups is not None else None
                item_spans = (
                    _inline_spans([kept[k] for k in rows], [lines[k] for k in rows], False)
                    if rows is not None
                    else []
                )
                out.append(_logical(len(out), block, item, spans=item_spans))
            continue
        out.append(_logical(len(out), block, text))
    for lb in out:
        lb.text = lb.text.rstrip(SOFT_HYPHEN)  # a soft hyphen no later block joined onto
        lb.math_spans = _shift(lb.math_spans, 0, len(lb.text), 0)
        if lb.type in CONTENT_MATH_TYPES:
            # an italic variable inside text-font maths ("x – μ") yields to the content span
            fonts = [sp for sp in lb.math_spans if not _variable_span(sp)]
            found = content_spans(lb.text, fonts)
            if found:
                kept = [
                    sp
                    for sp in lb.math_spans
                    if not _variable_span(sp)
                    or not any(f.start < sp.end and sp.start < f.end for f in found)
                ]
                lb.math_spans = sorted([*kept, *found], key=lambda sp: sp.start)
    return out


def _size(block: Block) -> float:
    return max((s.size for ln in block.lines for s in ln.spans), default=0.0)


def _logical(
    id_: int,
    block: Block,
    text: str,
    raw: str | None = None,
    spans: list[MathSpan] | None = None,
) -> LogicalBlock:
    return LogicalBlock(
        id=id_,
        page=block.page,
        type=block.type,
        text=text,
        source=[(block.page, block.index)],
        raw_text=raw,
        math_spans=list(spans or []),
    )
