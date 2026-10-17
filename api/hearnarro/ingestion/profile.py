"""Document profile (ING-11, D40): how mathematical a document is, computed once per document.

The pass runs between stage 4 (``merge_blocks``) and stage 5 (``split_sentences``) in
``ingest()``: stage 5's normalizer already needs the class for the bracket rule ("[12]" is a
citation in prose, "[0, 1]" is an interval inside maths). The result is stored as
``documents.profile_json`` and can be overridden per document (LIB-1 badge), which
re-normalizes the stored segments without re-ingesting.

Shares are over the characters a listener would hear: every block whose type is read
(``_READ_TYPES``); an equation or table block counts its raw merged text (``raw_text``), not
its spoken cue. Inline maths mass is the larger of the inline (non-display) ``LogicalBlock.math_spans``
characters (MATH-2) and the characters of prose tokens that carry a maths glyph (Unicode
``Sm``, Greek, mathematical alphanumerics; their share is also ``inline_token_share``). The
token estimate is the floor because OCR pages carry no span geometry.

Tuning on the 30 gate (e) fixtures (``_agent/results/677``..``681``), D40's first thresholds
matched 17 of 30. Three changes, each a reading of D40 rather than a new rule:

- a display equation is a run of consecutive ``equation`` blocks (stage 3 splits one display
  into rows), and the per-page bar is 2 such runs, not 1 row;
- dense inline maths alone makes a document ``math`` (``inline_token_share`` >= 4 %): textbook
  pages set their formulas inline or in list items, so they have no ``equation`` block;
- ``prose`` is maths mass under 1 % (not 2 %), fewer than 1 display per page (not zero), and a
  code share under 10 %. Until ING-10's ``code`` blocks exist, code share is the share of
  text-layer glyphs set in a monospace font: a code listing is not prose (its brackets index).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from typing import Literal, cast

from hearnarro.ingestion.models import LogicalBlock, Page

ProfileClass = Literal["prose", "mixed", "math"]
CitationStyle = Literal["numeric", "author_year", "none"]
PROFILE_CLASSES: tuple[ProfileClass, ...] = ("prose", "mixed", "math")

# D40 thresholds (tunable on the fixtures; any change is reported with before/after match counts).
MATH_SHARE_MATH = 0.15  # maths chars / read chars at or above this -> math
DISPLAY_PER_PAGE_MATH = 2.0  # display equations (runs of equation blocks) per page -> math
INLINE_TOKEN_SHARE_MATH = 0.04  # prose tokens carrying a maths glyph at or above -> math
MATH_SHARE_PROSE = 0.01  # below this ...
DISPLAY_PER_PAGE_PROSE = 1.0  # ... and fewer displays per page than this ...
CODE_SHARE_PROSE = 0.10  # ... and less code than this -> prose
CITATION_MIN = 3  # a citation style needs at least this many matches

_READ_TYPES = frozenset({"heading", "body", "caption", "footnote", "table", "equation", "list"})
_PROSE_TYPES = frozenset({"heading", "body", "caption", "footnote", "list"})
_MONOSPACE = re.compile(r"mono|courier|consol|menlo|typewriter|cmtt|inconsolata", re.IGNORECASE)
_NUMERIC_CITATION = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")  # normalize._PATTERN "citation"
_AUTHOR_YEAR = re.compile(r"\((?:[A-Z][\w'’-]+(?: et al\.)?(?:,| and| &)?\s?)+,? \d{4}[a-z]?\)")


@dataclass(frozen=True)
class DocumentProfile:
    math_share: float  # (equation block chars + inline maths span chars) / all read chars
    display_per_page: float  # display equation blocks / pages with a text layer
    code_share: float  # code block chars / all read chars (ING-10)
    citation_style: CitationStyle
    scanned_share: float  # pages with has_text_layer False / pages (ING-2)
    cls: ProfileClass  # computed class
    inline_token_share: float = 0.0  # prose tokens with a maths glyph / prose tokens
    override: ProfileClass | None = None  # user's class (LIB-1 badge); wins when set
    author_year_citations: Literal["read", "skip"] = "read"  # TERM-3 toggle

    @property
    def effective(self) -> ProfileClass:
        return self.override or self.cls

    def with_override(
        self, cls: ProfileClass | None, author_year: Literal["read", "skip"] | None = None
    ) -> DocumentProfile:
        return replace(
            self,
            override=cls,
            author_year_citations=author_year or self.author_year_citations,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, s: str | None) -> DocumentProfile:
        """``None`` (a document ingested before migration 0005) reads as ``PROSE_DEFAULT``."""
        if not s:
            return PROSE_DEFAULT
        data = json.loads(s)
        return cls(
            math_share=float(data.get("math_share", 0.0)),
            display_per_page=float(data.get("display_per_page", 0.0)),
            code_share=float(data.get("code_share", 0.0)),
            citation_style=cast(CitationStyle, data.get("citation_style", "none")),
            scanned_share=float(data.get("scanned_share", 0.0)),
            cls=cast(ProfileClass, data.get("cls", "prose")),
            inline_token_share=float(data.get("inline_token_share", 0.0)),
            override=cast("ProfileClass | None", data.get("override")),
            author_year_citations=cast(
                Literal["read", "skip"], data.get("author_year_citations", "read")
            ),
        )


# What a document ingested before M5 behaves as: today's rules (citations dropped).
PROSE_DEFAULT = DocumentProfile(
    math_share=0.0,
    display_per_page=0.0,
    code_share=0.0,
    citation_style="none",
    scanned_share=0.0,
    cls="prose",
)


def classify(
    math_share: float,
    display_per_page: float,
    inline_token_share: float = 0.0,
    code_share: float = 0.0,
) -> ProfileClass:
    """D40 as tuned on the fixtures: ``math`` at >= 15 % maths mass, >= 2 displays per page or
    >= 4 % maths tokens; ``prose`` under 1 % maths mass, under 1 display per page and under
    10 % code; ``mixed`` otherwise."""
    if (
        math_share >= MATH_SHARE_MATH
        or display_per_page >= DISPLAY_PER_PAGE_MATH
        or inline_token_share >= INLINE_TOKEN_SHARE_MATH
    ):
        return "math"
    if (
        math_share < MATH_SHARE_PROSE
        and display_per_page < DISPLAY_PER_PAGE_PROSE
        and code_share < CODE_SHARE_PROSE
    ):
        return "prose"
    return "mixed"


def _is_math_char(c: str) -> bool:
    o = ord(c)
    return (
        unicodedata.category(c) == "Sm"
        or 0x370 <= o <= 0x3FF
        or 0x1D400 <= o <= 0x1D7FF
        or c in "^_√∑∏∫∂∞≈≠≤≥±×÷·′"
    )


def _span_chars(spans: Sequence[object]) -> int:
    total = 0
    for span in spans:
        start = getattr(span, "start", None)
        end = getattr(span, "end", None)
        if start is None or end is None:
            start, end = cast("tuple[int, int]", span)[:2]
        total += max(0, int(end) - int(start))
    return total


def _display_runs(blocks: Sequence[LogicalBlock]) -> int:
    """Runs of consecutive read ``equation`` blocks: one display split into rows counts once."""
    runs, prev = 0, False
    for b in blocks:
        is_eq = b.type == "equation"
        if is_eq and not prev:
            runs += 1
        prev = is_eq
    return runs


def _monospace_share(pages: Sequence[Page]) -> float:
    total = mono = 0
    for page in pages:
        for block in page.blocks:
            for line in block.lines:
                for span in line.spans:
                    n = len(span.text.strip())
                    total += n
                    if _MONOSPACE.search(span.font):
                        mono += n
    return mono / total if total else 0.0


def citation_style(texts: Sequence[str]) -> CitationStyle:
    numeric = sum(len(_NUMERIC_CITATION.findall(t)) for t in texts)
    author_year = sum(len(_AUTHOR_YEAR.findall(t)) for t in texts)
    if max(numeric, author_year) < CITATION_MIN:
        return "none"
    return "numeric" if numeric >= author_year else "author_year"


def compute_profile(pages: list[Page], blocks: list[LogicalBlock]) -> DocumentProfile:
    """Shares and class of one document (ING-11); pure, so the eval runner can call it."""
    read = [b for b in blocks if b.type in _READ_TYPES or b.type == "code"]
    prose = [b.text for b in read if b.type in _PROSE_TYPES]
    total = sum(len(b.raw_text or b.text) for b in read)
    eq_chars = sum(len(b.raw_text or b.text) for b in read if b.type == "equation")
    tokens = " ".join(prose).split()
    math_tokens = [t for t in tokens if any(_is_math_char(c) for c in t)]
    # The token share is over the words of every read block but the equations: a code listing's
    # words count in ``total`` (its raw text), so they count here too, or a short docs page with
    # one line of maths in its prose reads as dense maths (formula_08, m5-p3f).
    code_words = sum(len((b.raw_text or "").split()) for b in read if b.type == "code")
    # Inline mass: inline (non-display) MathSpans with geometry only (maths-font runs), since a
    # display span covers an equation block already counted in eq_chars and a content span
    # (``merge.content_spans``, no runs) spans the operands around a text-font glyph, words the
    # token estimate already weighs. The token estimate is the floor (and the only measure on
    # OCR pages, which carry no span geometry).
    inline_spans = [
        s
        for b in read
        for s in (getattr(b, "math_spans", None) or ())
        if not s.display and getattr(s, "runs", None)
    ]
    inline = max(_span_chars(inline_spans), sum(len(t) for t in math_tokens))
    code_chars = sum(len(b.raw_text or b.text) for b in read if b.type == "code")
    code_share = code_chars / total if code_chars and total else _monospace_share(pages)
    text_pages = sum(1 for p in pages if p.has_text_layer) or len(pages) or 1
    math_share = (eq_chars + inline) / total if total else 0.0
    display_per_page = _display_runs(read) / text_pages
    words = len(tokens) + code_words
    inline_share = len(math_tokens) / words if words else 0.0
    scanned = sum(1 for p in pages if not p.has_text_layer) / len(pages) if pages else 0.0
    return DocumentProfile(
        math_share=round(math_share, 4),
        display_per_page=round(display_per_page, 4),
        code_share=round(code_share, 4),
        citation_style=citation_style([b.text for b in read if b.type != "heading"]),
        scanned_share=round(scanned, 4),
        cls=classify(math_share, display_per_page, inline_share, code_share),
        inline_token_share=round(inline_share, 4),
    )
