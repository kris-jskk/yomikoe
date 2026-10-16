"""Stage 3: reading order, two-column detection (D2, D3, ING-4)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, Page

READ_TYPES = {"body", "heading", "list", "caption", "equation", "table"}


def detect_columns(
    blocks: list[Block],
    page_width: float,
    *,
    gap_frac: float = 0.08,
    full_width_frac: float = 0.60,
) -> tuple[int, float | None]:
    """Return (n_columns, split_x); split_x is None for one column."""
    raise NotImplementedError


def order_page(page: Page, *, gap_frac: float = 0.08, full_width_frac: float = 0.60) -> list[Block]:
    """Readable blocks of one page in reading order, footnotes last."""
    raise NotImplementedError


def order_document(pages: list[Page]) -> list[Block]:
    """Concatenation of order_page over pages."""
    raise NotImplementedError
