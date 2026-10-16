"""Stage 4: merge lines and cross-page blocks (ING-5)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, LogicalBlock

TERMINAL_PUNCT = '.!?:;"”’'
# Non-body types that end a cross-page join candidate: a new section or a list
# interrupts the sentence. Other non-body types (footer, footnote, caption, ...) are skipped.
JOIN_BLOCKERS = {"heading", "list"}


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


def _continues(prev_text: str, next_text: str) -> bool:
    prev = prev_text.rstrip()
    nxt = next_text.lstrip()
    if not prev or not nxt:
        return False
    return nxt[0].islower() or prev[-1] not in TERMINAL_PUNCT


def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]:
    """One LogicalBlock per Block, joining body blocks that continue across a page break.

    Block B (first body block of page N+1) joins block A (last body block of page N) when
    only non-body blocks other than headings and lists lie between them and B starts
    lowercase or A lacks terminal punctuation.
    """
    out: list[LogicalBlock] = []
    candidate: int | None = None  # index in ``out`` of the last body block seen
    candidate_page = -1
    for block in blocks:
        text = merge_lines([ln.text for ln in block.lines])
        if block.type == "body":
            if (
                candidate is not None
                and block.page == candidate_page + 1
                and _continues(out[candidate].text, text)
            ):
                target = out[candidate]
                target.text = merge_lines([target.text, text])
                target.source.append((block.page, block.index))
            else:
                out.append(
                    LogicalBlock(
                        id=len(out),
                        page=block.page,
                        type="body",
                        text=text,
                        source=[(block.page, block.index)],
                    )
                )
                candidate = len(out) - 1
            candidate_page = block.page
            continue
        if block.type in JOIN_BLOCKERS:
            candidate = None
        out.append(
            LogicalBlock(
                id=len(out),
                page=block.page,
                type=block.type,
                text=text,
                source=[(block.page, block.index)],
            )
        )
    return out
