"""Data model shared by every ingestion stage (ING-2..ING-6).

See _agent/specs/m1-ingestion-interfaces.md and docs/TECHNICAL_DESIGN.md, "Segment model".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in PDF points, origin top-left (PyMuPDF convention)."""

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
    dir: tuple[float, float] = (1.0, 0.0)  # PyMuPDF line "dir"; anything else is rotated text

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
]


@dataclass
class Block:
    page: int  # 0-based page number
    index: int  # position in PyMuPDF's block list for that page
    bbox: BBox
    lines: list[Line]
    type: BlockType = "body"
    ocr: bool = False  # True when produced by OCR (ING-2)
    inline: bool = False  # set by stage 3: continues the previous block's text line (ING-4)

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
    has_text_layer: bool = True


@dataclass
class LogicalBlock:
    """Output of stage 4: one readable unit after line/page merging."""

    id: int  # 0..N-1, reading order across the document
    page: int  # page of the first source block
    type: BlockType
    text: str  # merged text (lines joined, de-hyphenated, cross-page joined)
    source: list[tuple[int, int]]  # (page, block.index) of every raw block merged in


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
