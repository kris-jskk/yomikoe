"""Stage 4: merge lines and cross-page blocks (ING-5)."""

from __future__ import annotations

import re

from hearnarro.ingestion.classify import BOILERPLATE_RE, EMAIL
from hearnarro.ingestion.models import Block, LogicalBlock
from hearnarro.ingestion.segment import _segmenter

TERMINAL_PUNCT = '.!?:;"”’'
# Non-body types that end a join candidate: a new section, a list or a display equation
# interrupts the sentence. Other non-body types (footnote, caption, table, ...) are floats.
JOIN_BLOCKERS = {"heading", "list", "equation"}
FLOAT_SIZE_RATIO = 0.85  # body text this much smaller than the open paragraph is a label
EMAIL_TOKEN_RE = re.compile(
    r"\{[^}]*\}\s*@[\w-]+(?:\.[\w-]+)+|[\w.+-]+(?:,\s?[\w.+-]+)*@[\w-]+(?:\.[\w-]+)+"
)
ABSTRACT_RE = re.compile(r"^\s*abstract\b", re.IGNORECASE)
EMAIL_ONLY_RE = re.compile(rf"^{EMAIL}(?:[\s,;]+{EMAIL})*[\s,;.]*$")


def merge_lines(lines: list[str]) -> str:
    """Join lines with spaces, de-hyphenating before a lowercase continuation."""
    parts = [" ".join(line.split()) for line in lines]
    out = ""
    for part in parts:
        if not part:
            continue
        if out.endswith("-") and part[0].islower():
            out = out[:-1] + part
        elif out:
            out = out + " " + part
        else:
            out = part
    return out


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
    B starts lowercase, or B is on the next page and A lacks terminal punctuation. When
    floats lie between A and B only B's first sentence moves up into A; the rest of B stays
    after the floats. Email-only and boilerplate lines (``is_noise_line``) are dropped, and
    on page 0 before the "Abstract" heading (the author block) email tokens are stripped
    from every line ("AI Singapore, Singapore a,b@x.org" -> "AI Singapore, Singapore").
    """
    in_author_block = True
    out: list[LogicalBlock] = []
    candidate: int | None = None  # index in ``out`` of the last body block seen
    last_body: Block | None = None
    for block in blocks:
        lines = [ln.text for ln in block.lines if not is_noise_line(ln.text)]
        if block.page > 0 or ABSTRACT_RE.match(block.text):
            in_author_block = False
        if in_author_block and block.type in ("heading", "body"):
            lines = [strip_emails(ln) for ln in lines]
        text = merge_lines(lines)
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
                and block.page in (last_body.page, last_body.page + 1)
                and _is_flow_break(last_body, block)
                and _continues(out[candidate].text, text, block.page != last_body.page)
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
        out.append(_logical(len(out), block, text))
    return out


def _size(block: Block) -> float:
    return max((s.size for ln in block.lines for s in ln.spans), default=0.0)


def _logical(id_: int, block: Block, text: str) -> LogicalBlock:
    return LogicalBlock(
        id=id_, page=block.page, type=block.type, text=text, source=[(block.page, block.index)]
    )
