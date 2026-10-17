"""Stage 4: merge lines and cross-page blocks (ING-5)."""

from __future__ import annotations

import re

from hearnarro.ingestion.classify import BOILERPLATE_RE, EMAIL
from hearnarro.ingestion.models import (
    BULLET_GLYPHS,
    INLINE_ITEM_RE,
    ITEM_RE,
    Block,
    Line,
    LogicalBlock,
    Span,
)
from hearnarro.ingestion.segment import _segmenter

TERMINAL_PUNCT = '.!?:;"”’'
# Non-body types that end a join candidate: a new section, a list or a display equation
# interrupts the sentence. Other non-body types (footnote, caption, table, ...) are floats.
JOIN_BLOCKERS = {"heading", "list", "equation"}
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
    parts = [" ".join(line.split()) for line in lines]
    out = ""
    for part in parts:
        if not part:
            continue
        if out.endswith(SOFT_HYPHEN) or (out.endswith(LINE_END_HYPHENS) and part[0].islower()):
            out = out[:-1] + part
        elif heading and out.endswith(LINE_END_HYPHENS):
            out = out + part
        elif out:
            out = out + " " + part
        else:
            out = part
    return out


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
        lines = [ln.text for ln in block.lines if not is_noise_line(ln.text)]
        if block.page > 0 or ABSTRACT_RE.match(block.text):
            in_author_block = False
        if in_author_block and block.type in ("heading", "body"):
            lines = [strip_emails(ln) for ln in lines]
        text = merge_lines(lines, heading=block.type == "heading")
        if block.inline and out and text:
            # Stage 3 found this block continuing the previous block's text line (inline maths).
            out[-1].text = merge_lines([out[-1].text, text])
            out[-1].source.append((block.page, block.index))
            continue
        if (
            block.type in ("body", "heading")
            and last_body is not None
            and candidate is not None
            and _size(block) < FLOAT_SIZE_RATIO * _size(last_body)
        ):
            # Small-print body or heading text (figure labels) between fragments is a float.
            out.append(_logical(len(out), block, text))
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
                target.text = merge_lines([target.text, head])
                target.source.append((block.page, block.index))
                if rest:
                    out.append(_logical(len(out), block, rest))
                    candidate = len(out) - 1
            else:
                out.append(_logical(len(out), block, text))
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
            # ING-7: one cue segment; the symbols are never spoken.
            out.append(_logical(len(out), block, equation_cue(lines), raw=text))
            continue
        if block.type == "list":
            for item in split_items(lines):
                out.append(_logical(len(out), block, item))
            continue
        out.append(_logical(len(out), block, text))
    for lb in out:
        lb.text = lb.text.rstrip(SOFT_HYPHEN)  # a soft hyphen no later block joined onto
    return out


def _size(block: Block) -> float:
    return max((s.size for ln in block.lines for s in ln.spans), default=0.0)


def _logical(id_: int, block: Block, text: str, raw: str | None = None) -> LogicalBlock:
    return LogicalBlock(
        id=id_,
        page=block.page,
        type=block.type,
        text=text,
        source=[(block.page, block.index)],
        raw_text=raw,
    )
