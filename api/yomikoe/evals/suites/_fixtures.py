"""Fixture PDFs shared by the tier-0 suites: manifest, expected prose and one cached ingest."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import yomikoe
from yomikoe.evals.scorers import excluded_actual_texts, prose_only

# The PDFs stay in the test fixtures (D32); the venv is an editable install of api/.
FIXTURES = Path(yomikoe.__file__).resolve().parents[1] / "tests" / "fixtures" / "pdfs"


def manifest() -> list[dict[str, Any]]:
    """Manifest entries in file order: name, class, source, licence, pages."""
    return json.loads((FIXTURES / "manifest.json").read_text())


M1_CLASSES = ("academic", "report", "scanned", "tables")


def entries(
    classes: tuple[str, ...] | None = None, *, skip_scanned: bool = False
) -> list[dict[str, Any]]:
    """Manifest entries filtered by class; EVAL-2/3 need ``sentences.txt`` so pass ``M1_CLASSES``."""
    return [
        e
        for e in manifest()
        if (classes is None or e["class"] in classes)
        and not (skip_scanned and e["class"] == "scanned")
    ]


def expected_rows(name: str) -> list[tuple[str, str]]:
    """(type, text) rows of ``<name>.expected.jsonl``."""
    path = FIXTURES / f"{name}.expected.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [(r["type"], r["text"]) for r in rows]


def truth_sentences(name: str) -> list[str]:
    """Reviewed sentences of ``<name>.sentences.txt``, one per line."""
    return (FIXTURES / f"{name}.sentences.txt").read_text().splitlines()


@cache
def ingest_result(name: str) -> Any:
    """The ``IngestResult`` of one ``ingest()`` call, cached so EVAL-1..3 parse a PDF once."""
    from yomikoe.ingestion.pipeline import ingest

    return ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)


@cache
def ingested(name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(prose segment texts, excluded texts for the D14 guard) of the cached ingest."""
    result = ingest_result(name)
    block_type = {b.id: b.type for b in result.blocks}
    prose, _ = prose_only((block_type[s.block_id], s.text) for s in result.segments)
    excluded = excluded_actual_texts(result.blocks, result.segments)
    return tuple(prose), tuple(excluded)
