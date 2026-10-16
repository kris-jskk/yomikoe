"""Stage 4: merge lines and cross-page blocks (ING-5)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, LogicalBlock


def merge_lines(lines: list[str]) -> str:
    """Join lines with spaces, de-hyphenating before a lowercase continuation."""
    raise NotImplementedError


def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]:
    """One LogicalBlock per Block, joining body blocks that continue across a page break."""
    raise NotImplementedError
