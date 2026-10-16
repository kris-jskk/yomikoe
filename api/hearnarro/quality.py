"""Document quality checklist (M1): run on every document after ingestion.

Each check looks at the pipeline's output segments (text + the type of the block they came
from) and returns a ``CheckResult``: name, count, measured value, threshold, pass/fail and up
to five example strings. A check with ``threshold=None`` is informational and always passes.
The document passes when every thresholded check passes.

The checks encode defects found on user documents (TECHNICAL_DESIGN stages 1-4, 2026-10-16;
docs/guide/m1-ingest-map.html phase 8):

1. dangling_hyphens        "inter- national": a line-end hyphen not joined (ING-4)
2. ligature_artifacts      "e!ect", "di#erent": ligature glyphs mapped to ASCII punctuation
3. single_letter_segments  a drop cap split from its word ("W" / "e start")
   (chapter_number_segments: one-digit segments, informational only)
4. tracked_lines           letter-spaced text ("C H A P T E R")
5. leader_dots             table-of-contents leaders (". . . . " or "....."), only in a
                           segment that is >= 60% dots/spaces (not a math ellipsis)
6. midsentence_breaks      a body sentence split across segments (ratio to body segments)
7. toc_leak                table-of-contents entries read after a "Contents" heading
8. punctuation_only        segments with no letter or digit (informational until M2)
9. duplicate_runs          the same segment twice in a row, or a repeated nearby heading
                           (informational)
10. title_filename_like    the chosen title looks like a file name
11. empty_text_document    a PDF with a text layer that yields no segments

Known false positives excluded: a suspended hyphen ("16K- and 65K-token"), "#" or "!" inside
a URL, and a math ellipsis (". . . ,") inside prose.

Not checked: off-page text leaks (text outside the page box). Stage 1 drops it before any
segment exists, so it cannot be observed after the pipeline.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_EXAMPLES = 5
PROSE_TYPES = frozenset({"heading", "body", "list", "caption", "footnote"})
# Block types whose text is never read aloud; their segments are not checked.
UNREAD_TYPES = frozenset({"header", "footer", "noise", "figure", "toc", "image"})

# a suspended hyphen ("16K- and 65K-token", "pre- or post-war") is correct English
DANGLING_HYPHEN_RE = re.compile(r"[A-Za-z][‐‑-] (?!(?:and|or|to|nor)\b)[a-z]")
LIGATURE_RE = re.compile(r"[A-Za-z][!#$%][a-z]")
SINGLE_LETTER_RE = re.compile(r"^[A-Za-z]$")
SINGLE_DIGIT_RE = re.compile(r"^[0-9]$")
TRACKED_RE = re.compile(r"([A-Za-z] ){5,}[A-Za-z]")
LEADER_RE = re.compile(r"(\. ){4,}|\.{5,}")
LEADER_MIN_SHARE = 0.6  # dots + spaces as a share of the segment's characters
URL_MARKERS = ("://", "www.", "@")
TRAILING_PUNCT = ".,;:!?)]}\"'”’"
SENTENCE_END_RE = re.compile(r"[.!?:;\"”’)\]]$")
LOWER_START_RE = re.compile(r"^[(\[\"'“‘]?[a-z]")
TOC_MARKERS = frozenset({"contents", "table of contents"})
TOC_WINDOW = 60
PAGE_NUMBER_END_RE = re.compile(r"\s\d{1,4}$|^\d{1,4}$|^[ivxlc]+$")
DUPLICATE_MIN_CHARS = 12
HEADING_WINDOW = 20
MIDSENTENCE_MAX_RATIO = 0.01
MIN_SEGMENTS_FOR_TITLE = 5
TEXT_LAYER_MIN_CHARS = 200


@dataclass(frozen=True)
class QSeg:
    """What the checks need from a segment: its text and its block's type."""

    text: str
    type: str


@dataclass
class CheckResult:
    name: str
    count: int
    threshold: float | None  # None: informational
    passed: bool
    examples: list[str] = field(default_factory=list)
    value: float | None = None  # the measured value compared with the threshold

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class QualityReport:
    source: str
    title: str | None
    segments: int
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "title": self.title,
            "segments": self.segments,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
        }

    def table(self) -> str:
        rows = [f"{'check':<26} {'count':>6} {'value':>8} {'thr':>6}  result  examples"]
        for c in self.checks:
            thr = "-" if c.threshold is None else f"{c.threshold:g}"
            val = "" if c.value is None else f"{c.value:.4g}"
            res = "info" if c.threshold is None else ("PASS" if c.passed else "FAIL")
            ex = " | ".join(e[:60] for e in c.examples[:3])
            rows.append(f"{c.name:<26} {c.count:>6} {val:>8} {thr:>6}  {res:<6}  {ex}")
        head = f"{self.source}: {self.segments} segments, title {self.title!r}"
        return "\n".join([head, *rows, f"OVERALL {'PASS' if self.passed else 'FAIL'}"])


def _read(segs: Sequence[QSeg]) -> list[QSeg]:
    return [s for s in segs if s.type not in UNREAD_TYPES]


def _count(name: str, hits: list[str], threshold: float | None = 0) -> CheckResult:
    n = len(hits)
    passed = threshold is None or n <= threshold
    return CheckResult(name, n, threshold, passed, hits[:MAX_EXAMPLES], float(n))


def _regex_check(name: str, pattern: re.Pattern[str]) -> Callable[[Sequence[QSeg]], CheckResult]:
    def check(segs: Sequence[QSeg]) -> CheckResult:
        return _count(name, [s.text for s in _read(segs) if pattern.search(s.text)])

    check.__name__ = f"check_{name}"
    return check


check_dangling_hyphens = _regex_check("dangling_hyphens", DANGLING_HYPHEN_RE)
check_tracked_lines = _regex_check("tracked_lines", TRACKED_RE)


def _url_like(token: str) -> bool:
    """A token that is (part of) a URL or e-mail address.

    "://", "www." or "@" anywhere; or a "#" between letters in a token that also has a "/" or
    an inner "." (a sentence-final period does not count, so "di#erent." stays a hit).
    """
    if any(m in token for m in URL_MARKERS):
        return True
    core = token.rstrip(TRAILING_PUNCT)
    return bool(re.search(r"[A-Za-z]#[A-Za-z]", core)) and ("/" in core or "." in core)


def _ligature_hit(text: str) -> bool:
    prev = ""
    for tok in text.split():
        # a URL broken by a space ("https://angel.co/syndicates/ for-investors#syndicates")
        url_tail = _url_like(prev) and prev.endswith("/") and "#" in tok
        if LIGATURE_RE.search(tok) and not (_url_like(tok) or url_tail):
            return True
        prev = tok
    return False


def check_ligature_artifacts(segs: Sequence[QSeg]) -> CheckResult:
    """Ligature glyphs ("e!ect", "di#erent"); tokens that look like URLs or e-mail addresses are skipped."""
    return _count("ligature_artifacts", [s.text for s in _read(segs) if _ligature_hit(s.text)])


def check_leader_dots(segs: Sequence[QSeg]) -> CheckResult:
    """TOC leaders; a segment counts only when >= 60% of it is dots and spaces."""

    def leader(text: str) -> bool:
        if not text or not LEADER_RE.search(text):
            return False
        return sum(c in ". " for c in text) / len(text) >= LEADER_MIN_SHARE

    return _count("leader_dots", [s.text for s in _read(segs) if leader(s.text)])


def check_single_letter_segments(segs: Sequence[QSeg]) -> CheckResult:
    hits = [s.text for s in segs if s.type in PROSE_TYPES and SINGLE_LETTER_RE.match(s.text)]
    return _count("single_letter_segments", hits)


def check_chapter_number_segments(segs: Sequence[QSeg]) -> CheckResult:
    """One-digit segments are chapter numbers: counted, never failed."""
    hits = [s.text for s in segs if s.type in PROSE_TYPES and SINGLE_DIGIT_RE.match(s.text)]
    return _count("chapter_number_segments", hits, threshold=None)


def check_midsentence_breaks(segs: Sequence[QSeg]) -> CheckResult:
    """Consecutive body segments A, B where A has no sentence end and B starts lowercase."""
    read = _read(segs)
    n_body = sum(1 for s in read if s.type == "body")
    hits = [
        f"{a.text} || {b.text}"
        for a, b in itertools.pairwise(read)
        if a.type == "body"
        and b.type == "body"
        and not SENTENCE_END_RE.search(a.text.rstrip())
        and LOWER_START_RE.match(b.text)
    ]
    ratio = len(hits) / n_body if n_body else 0.0
    return CheckResult(
        "midsentence_breaks",
        len(hits),
        MIDSENTENCE_MAX_RATIO,
        ratio <= MIDSENTENCE_MAX_RATIO,
        hits[:MAX_EXAMPLES],
        round(ratio, 4),
    )


def check_toc_leak(segs: Sequence[QSeg]) -> CheckResult:
    """Segments ending in a page number within 60 segments after a "Contents" segment."""
    read = _read(segs)
    flagged: set[int] = set()
    for i, s in enumerate(read):
        if s.text.strip().lower() in TOC_MARKERS:
            for j in range(i + 1, min(i + 1 + TOC_WINDOW, len(read))):
                if PAGE_NUMBER_END_RE.search(read[j].text.strip()):
                    flagged.add(j)
    return _count("toc_leak", [read[j].text for j in sorted(flagged)])


def check_punctuation_only(segs: Sequence[QSeg]) -> CheckResult:
    """Segments with no letter or digit. Informational until M2.

    Most hits today are a closing quote split off by the sentence splitter ('”' as its own
    segment), which is an M2 sentence-boundary issue; this check becomes thresholded in M2
    together with the boundary metric.
    """
    hits = [s.text for s in _read(segs) if not any(c.isalnum() for c in s.text)]
    return _count("punctuation_only", hits, threshold=None)


def check_duplicate_runs(segs: Sequence[QSeg]) -> CheckResult:
    """Identical consecutive texts (>= 12 chars); a heading repeated within 20 segments.

    Informational: legitimate repeats are common (a book's cover, title page and chapter 1
    heading; a NIST cover page and inner title page), so a count cannot tell a defect apart.
    """
    read = _read(segs)
    hits: list[str] = []
    for a, b in itertools.pairwise(read):
        if a.text == b.text and len(a.text) >= DUPLICATE_MIN_CHARS:
            hits.append(b.text)
    for i, s in enumerate(read):
        if s.type != "heading":
            continue
        window = read[max(0, i - HEADING_WINDOW) : i]
        repeated = any(p.type == "heading" and p.text == s.text for p in window)
        # skip a heading already counted as a consecutive duplicate
        consecutive = read[i - 1].text == s.text and len(s.text) >= DUPLICATE_MIN_CHARS
        if repeated and not consecutive:
            hits.append(s.text)
    return _count("duplicate_runs", hits, threshold=None)


def check_title_filename_like(title: str | None, segs: Sequence[QSeg]) -> CheckResult:
    from hearnarro.storage.jobs import FILENAME_TITLE_RE

    t = (title or "").strip()
    bad = len(segs) >= MIN_SEGMENTS_FOR_TITLE and (
        bool(FILENAME_TITLE_RE.search(t)) or not any(c.isspace() for c in t)
    )
    return _count("title_filename_like", [t] if bad else [])


def check_empty_text_document(segs: Sequence[QSeg], *, max_page_chars: int) -> CheckResult:
    """A text layer (>= 200 chars on some page) but no segments."""
    bad = max_page_chars >= TEXT_LAYER_MIN_CHARS and not segs
    return _count("empty_text_document", [f"max page chars {max_page_chars}"] if bad else [])


def run_checks(
    segs: Sequence[QSeg], *, title: str | None, max_page_chars: int, source: str = ""
) -> QualityReport:
    checks = [
        check_dangling_hyphens(segs),
        check_ligature_artifacts(segs),
        check_single_letter_segments(segs),
        check_chapter_number_segments(segs),
        check_tracked_lines(segs),
        check_leader_dots(segs),
        check_midsentence_breaks(segs),
        check_toc_leak(segs),
        check_punctuation_only(segs),
        check_duplicate_runs(segs),
        check_title_filename_like(title, segs),
        check_empty_text_document(segs, max_page_chars=max_page_chars),
    ]
    return QualityReport(source, title, len(segs), checks)


def check_pdf(pdf_path: str | Path, *, ocr: bool = True) -> QualityReport:
    """Ingest a PDF and run every check; the title comes from ``choose_title``."""
    from hearnarro.ingestion.pipeline import ingest
    from hearnarro.storage.jobs import _first_heading, choose_title, pdf_title

    result = ingest(pdf_path, ocr=ocr)
    types = {b.id: b.type for b in result.blocks}
    segs = [QSeg(s.text, types[s.block_id]) for s in result.segments]
    title = choose_title(pdf_title(pdf_path), _first_heading(result), Path(pdf_path).name)
    max_chars = max(
        (
            sum(len(sp.text.strip()) for blk in p.blocks for ln in blk.lines for sp in ln.spans)
            for p in result.pages
            if p.has_text_layer
        ),
        default=0,
    )
    return run_checks(segs, title=title, max_page_chars=max_chars, source=Path(pdf_path).name)
