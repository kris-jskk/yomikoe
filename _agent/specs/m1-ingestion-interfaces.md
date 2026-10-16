# M1 ingestion interfaces (supervisor-owned)

Tests are written against this file before the code exists; the implementation must match it
exactly. Algorithms come from `docs/TECHNICAL_DESIGN.md`, "Ingestion pipeline" and "Segment
model"; requirement IDs from `docs/PRD.md`. Package root: `api/hearnarro/ingestion/`.
Run everything with `api/.venv/bin/python` (Python 3.11, deps installed). Use `import pymupdf`,
not `fitz`.

## models.py

```python
@dataclass(frozen=True)
class BBox:
    x0: float; y0: float; x1: float; y1: float
    # properties: width, height, x_mid, y_mid; method overlaps(other) -> bool

@dataclass
class Span:
    text: str; bbox: BBox; font: str; size: float
    bold: bool = False; italic: bool = False; superscript: bool = False

@dataclass
class Line:
    spans: list[Span]; bbox: BBox
    # property text -> "".join(s.text for s in spans)

BlockType = Literal["heading", "body", "caption", "footnote", "header", "footer",
                    "table", "equation", "list", "image"]

@dataclass
class Block:
    page: int                 # 0-based page number
    index: int                # position in PyMuPDF's block list for that page
    bbox: BBox
    lines: list[Line]
    type: BlockType = "body"
    ocr: bool = False         # True when produced by OCR (ING-2)
    # property text -> "\n".join(line.text for line in self.lines)   (raw, NOT merged)

@dataclass
class Page:
    number: int; width: float; height: float
    blocks: list[Block]
    image_bboxes: list[BBox] = field(default_factory=list)
    table_bboxes: list[BBox] = field(default_factory=list)
    has_text_layer: bool = True

@dataclass
class LogicalBlock:          # output of stage 4
    id: int                  # 0..N-1, reading order across the document
    page: int                # page of the first source block
    type: BlockType
    text: str                # merged text (lines joined, de-hyphenated, cross-page joined)
    source: list[tuple[int, int]]   # (page, block.index) of every raw block merged in

@dataclass
class Segment:               # exactly TECHNICAL_DESIGN "Segment model"
    id: int; document_id: int; block_id: int; order: int; section_id: int | None
    text: str; normalized_text: str; char_start: int; char_end: int; char_map: list[int]
```

## extract.py  (stage 1; D1; ING-2)

```python
class OCRUnavailable(RuntimeError): ...
def ocr_available() -> bool            # pytesseract importable AND tesseract binary on PATH
def page_from_dict(number: int, width: float, height: float, text_dict: dict,
                   image_bboxes: list[BBox] = (), table_bboxes: list[BBox] = ()) -> Page
    # pure: builds Page from a PyMuPDF page.get_text("dict") payload. Span flags: bit 1 (2) italic,
    # bit 4 (16) bold, bit 0 (1) superscript. Also treat font names containing "Bold"/"Italic" as such.
    # Blocks with type 1 (images) become image_bboxes entries, not Blocks.
def extract_pages(pdf_path: str | Path, *, ocr: bool = True, min_text_chars: int = 20) -> list[Page]
    # per page: text_dict; table_bboxes from page.find_tables() (catch exceptions -> []);
    # if total chars < min_text_chars: has_text_layer=False and, if ocr and ocr_available(),
    # rasterize at 300 dpi and run pytesseract.image_to_data -> same Block/Line/Span shape
    # (word boxes grouped by block_num/line_num, size = word box height, ocr=True);
    # if OCR not available: page keeps has_text_layer=False and an empty block list (no raise).
```

## classify.py  (stage 2; ING-3)

```python
PAGE_NUMBER_RE   # matches ^\d+$, ^Page \d+, ^\d+ of \d+$ (case-insensitive, stripped)
def normalize_key(text: str) -> str          # lowercase, collapse whitespace, strip digits? NO: keep digits, strip whitespace only
def body_median_size(pages: list[Page]) -> float   # median span size across the DOCUMENT, each span weighted by len(text)
def repeated_band_texts(pages: list[Page], *, band_frac: float = 0.08, min_pages: int = 3) -> set[str]
    # normalize_key of blocks whose bbox lies fully in the top band (y1 <= band_frac*height) or bottom band
    # (y0 >= (1-band_frac)*height) and that appear on >= min_pages distinct pages
def classify_pages(pages: list[Page]) -> list[Page]
    # sets block.type in place, rules in TECHNICAL_DESIGN stage 2 table, first match wins:
    # header (top band) / footer (bottom band): repeated band text, or PAGE_NUMBER_RE match while in a band
    # heading: max span size >= 1.15 * body median, or (bold majority and <= 12 words and no terminal '.')
    # caption: ^(Figure|Fig\.|Table|Listing)\s*\d and within 40 pt of an image or table bbox
    # footnote: size <= 0.85 * median and y0 >= 0.75*height, or first span superscript digit
    # table: bbox overlaps a table_bbox
    # equation: > 50% of non-space chars in a math set (=+−-×÷∑∫√∂∞≤≥≈∝∈∀∃αβγδεθλμπσφω^_{}|) or font contains Math/CMSY/CMMI/CMEX
    # list: first line matches ^([•·▪‣◦\-–*]|\d+[.)])\s
    # body: else
```

## order.py  (stage 3; D2, D3; ING-4)

```python
READ_TYPES = {"body", "heading", "list", "caption", "equation", "table"}
def detect_columns(blocks: list[Block], page_width: float, *, gap_frac: float = 0.08,
                   full_width_frac: float = 0.60) -> tuple[int, float | None]
    # returns (n_columns, split_x). Ignores blocks wider than full_width_frac*page_width.
    # Two columns iff the x_mid values form two clusters (sort x_mids, largest gap between
    # consecutive values > gap_frac*page_width AND both sides non-empty); split_x = middle of that gap.
def order_page(page: Page, *, gap_frac=0.08, full_width_frac=0.60) -> list[Block]
    # keep READ_TYPES in column order; footnotes appended at the end of the page; header/footer/image dropped.
    # Full-width blocks (width > full_width_frac*page_width) are column breaks: emit col1 then col2 of the
    # blocks above it, then the full-width block, then continue. Within a column sort by bbox.y0.
def order_document(pages: list[Page]) -> list[Block]      # concatenation of order_page over pages
```

## merge.py  (stage 4; ING-5)

```python
def merge_lines(lines: list[str]) -> str
    # join with " "; if a line ends with "-" and the next line starts with a lowercase letter, drop the
    # hyphen and join with "". Collapse runs of whitespace to one space; strip ends.
def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]
    # one LogicalBlock per Block, except: if block A is the last block of page N and type body, and B is the
    # first body block of page N+1 (all blocks between are non-body), and (B.text starts lowercase OR A.text
    # does not end in one of .!?:;"”’) ) then A and B become one LogicalBlock (text joined per merge_lines).
    # ids are 0..N-1 in order.
```

## normalize.py  (stage 5 normalization; subset of ING-6)

```python
SPOKEN_ACRONYMS = {"NASA", "JSON", "SQL", "NATO", "UNESCO", "RAM", "ROM", "GPU", "CPU"} ...
def normalize(text: str) -> tuple[str, list[int]]
    # returns (normalized_text, char_map); len(char_map) == len(normalized_text); every value in
    # range(len(text)); char_map is non-decreasing. Unchanged characters map to themselves.
    # Rules (apply in this order, each on a token/regex match):
    #  - citation [12], [3, 4], [12–14]  -> dropped (no output chars)
    #  - "et al." -> "et al"
    #  - number% -> "<number> percent"   ("3.2%" -> "3.2 percent")
    #  - URL (https?://host/...) or www.host/... -> host only ("https://arxiv.org/abs/1" -> "arxiv.org")
    #  - ALL-CAPS token of 2-5 letters not in SPOKEN_ACRONYMS -> letters separated by spaces ("PDF" -> "P D F")
    #  - expanded output chars map to the input token: output char k of an expansion maps to
    #    input index  start + min(len(token)-1, k * len(token) // len(expansion))  (monotone, in range)
    # Whitespace left by a drop is collapsed to a single space, mapped to the original space.
```

## segment.py  (stage 5; D4; ING-5)

```python
def split_sentences(block: LogicalBlock, *, document_id: int, order_start: int, id_start: int) -> list[Segment]
    # pysbd.Segmenter(language="en", clean=False, char_span=True); each sentence -> Segment with
    # char_start/char_end into block.text such that block.text[char_start:char_end] == segment.text
    # (strip leading/trailing whitespace and adjust offsets accordingly); skip empty sentences;
    # normalized_text, char_map = normalize(text); section_id=None; block_id=block.id;
    # order = order_start + i; id = id_start + i.
```

## pipeline.py

```python
@dataclass
class IngestResult:
    pages: list[Page]; blocks: list[LogicalBlock]; segments: list[Segment]
def ingest(pdf_path: str | Path, *, document_id: int = 0, ocr: bool = True) -> IngestResult
    # extract_pages -> classify_pages -> order_document -> merge_blocks -> split_sentences over blocks
```

## cli.py  (M1 "CLI that dumps a PDF's segments to stdout")

`hearnarro dump <pdf> [--jsonl]`: plain mode prints `order<TAB>type<TAB>text` per segment; `--jsonl`
prints one JSON object per segment: `{"order", "page", "type", "text"}` (page/type from the segment's
LogicalBlock). `--jsonl` output IS the `name.expected.jsonl` format.

## Golden fixture format (D11)

`api/tests/fixtures/pdfs/manifest.json`: list of
`{"name": "<stem>", "class": "academic|report|scanned|tables", "two_column": bool, "source": "<url>", "license": "<spdx or 'public domain'>", "pages": int}`.
Each `<stem>.pdf` has `<stem>.expected.jsonl`, one line per segment in reading order, fields
`order, page, type, text`. The golden test compares only `text`, whitespace-collapsed and stripped,
as a sequence: `score = 1 - levenshtein(actual_seq, expected_seq) / len(expected_seq)`;
assert score >= 0.95 per PDF and mean >= 0.97. Class `scanned` is skipped when
`ocr_available()` is False (OCR fallback is M4 per PRD milestones).
