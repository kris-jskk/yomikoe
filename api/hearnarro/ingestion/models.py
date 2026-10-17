"""Data model shared by every ingestion stage (ING-2..ING-6).

See _agent/specs/m1-ingestion-interfaces.md and docs/TECHNICAL_DESIGN.md, "Segment model".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# List items (ING-3 classify, ING-5 merge, ING-6 normalize share these). Glyph bullets are
# silent when spoken; the hyphen, en dash and asterisk count only before a space, so
# "-based" (a hyphenated word wrapped to a line start) is not an item.
BULLET_GLYPHS = "•·▪▫■□●○◦‣►▶➢➤→⇒✓✔✗✘★☆"
DASH_BULLETS = "-–*"  # not "—": "— Wired" is an attribution line, not an item
# A line starting with a glyph, a dash/asterisk and a space, or a number, a letter or a
# lowercase roman numeral marker ("1." "1)" "(1)" "a." "a)" "(a)" "iv.") and a space.
_ENUM = r"(?:\d+|[a-z]|ii|iii|iv|vi{1,3}|ix|xi{1,3})"
ITEM_RE = re.compile(
    rf"^\s*(?:[{BULLET_GLYPHS}]|[{DASH_BULLETS}](?=\s)|{_ENUM}[.)](?=\s)|\({_ENUM}\)(?=\s))"
)
# The silent part of a glyph-bulleted item: leading space, the glyph(s), the space after.
GLYPH_BULLET_RE = re.compile(rf"^\s*(?:[{BULLET_GLYPHS}]+\s*|[{DASH_BULLETS}]\s+)")
# "→ a → b" on one line: a glyph between whitespace, then a word or an opening bracket or
# quote, starts another item ("≥· · · ≥λd", a dot-leader ellipsis in maths, does not).
INLINE_ITEM_RE = re.compile(rf"\s+(?=[{BULLET_GLYPHS}]\s+[\w(\[“‘\"'])")


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in PDF points, origin top-left, y grows downward."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def x_mid(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_mid(self) -> float:
        return (self.y0 + self.y1) / 2

    def overlaps(self, other: BBox) -> bool:
        """True when the two boxes share a region of positive area (touching edges do not count)."""
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )


@dataclass
class Span:
    text: str
    bbox: BBox
    font: str
    size: float
    bold: bool = False
    italic: bool = False
    superscript: bool = False


@dataclass
class Line:
    spans: list[Span]
    bbox: BBox
    dir: tuple[float, float] = (1.0, 0.0)  # reading direction; anything else is rotated text

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


BlockType = Literal[
    "heading",
    "body",
    "caption",
    "footnote",
    "header",
    "footer",
    "table",
    "equation",
    "list",
    "image",
    "noise",  # never read: rotated stamps, email/URL-only lines, cover boilerplate
    "figure",  # never read: text >= 80% inside a figure region (D12)
    "toc",  # never read: a table of contents (heading "Contents" and its entries)
    "code",  # ING-10: a code listing, spoken as one cue "Code listing, N lines."
]


@dataclass
class Block:
    page: int  # 0-based page number
    index: int  # position in stage 1's block list for that page
    bbox: BBox
    lines: list[Line]
    type: BlockType = "body"
    ocr: bool = False  # True when produced by OCR (ING-2)
    inline: bool = False  # set by stage 3: continues the previous block's text line (ING-4)
    lead: bool = False  # set by stage 2: read first on its page (a folded vertical title)

    @property
    def text(self) -> str:
        """Raw text, lines joined with newlines (not merged; merging is stage 4)."""
        return "\n".join(line.text for line in self.lines)


@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: list[Block]
    image_bboxes: list[BBox] = field(default_factory=list)
    table_bboxes: list[BBox] = field(default_factory=list)
    # D12: image bboxes plus unions of vector drawings covering 2%-80% of the page
    figure_bboxes: list[BBox] = field(default_factory=list)
    has_text_layer: bool = True
    text_chars: int = 0  # ING-2: non-space glyphs stage 1 found in the text layer


@dataclass
class MathSpan:
    """A run of maths inside ``LogicalBlock.text`` (MATH-1, MATH-2; spec m5 §3a).

    Invariant: ``block.text[start:end]`` equals the joined text of ``runs`` up to the
    whitespace (and line-end hyphens) ``merge_lines`` changes.
    """

    start: int  # offsets into LogicalBlock.text
    end: int
    display: bool  # True for a whole equation block, False for an inline span
    runs: list[Span]  # the stage 1 spans, in reading order, geometry kept
    label: str | None = None  # "3" from a trailing "(3)" (MATH-4)


@dataclass
class LogicalBlock:
    """Output of stage 4: one readable unit after line/page merging."""

    id: int  # 0..N-1, reading order across the document
    page: int  # page of the first source block
    type: BlockType
    text: str  # merged text (lines joined, de-hyphenated, cross-page joined)
    source: list[tuple[int, int]]  # (page, block.index) of every raw block merged in
    # ING-7: a table or equation block's text is spoken cues; this keeps the raw merged text so
    # the D14 excluded-mass guard can still weigh the table/equation characters.
    raw_text: str | None = None
    # MATH-1, MATH-2: maths runs inside ``text``, set by merge_blocks (spec m5 §3a).
    math_spans: list[MathSpan] = field(default_factory=list)


@dataclass
class Segment:
    """One sentence; exactly TECHNICAL_DESIGN "Segment model"."""

    id: int
    document_id: int
    block_id: int
    order: int
    section_id: int | None
    text: str
    normalized_text: str
    char_start: int
    char_end: int
    char_map: list[int]
