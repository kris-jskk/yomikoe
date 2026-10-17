"""M2 sentence-boundary measurement over the 15 text fixtures (ING-5, SYN-1).

Truth: `<stem>.sentences.txt`, one reviewed sentence per line, derived from
`<stem>.expected.jsonl` (prose types only, D12) with only line breaks moved. Parser side: the
prose segments of `ingest()`, same filter as the golden test. Metric: boundary precision,
recall and F1 over the aligned word stream (`tests/boundary_util.py`).

Thresholds (D18): per fixture F1 >= 0.90 and recall >= 0.97, mean F1 >= 0.95. The truth files
must also load and keep the expected word stream. The per-fixture table and mean are printed
(run with `-s`).
"""

import json
from functools import cache
from pathlib import Path

import pytest

from hearnarro.ingestion.pipeline import ingest
from tests.boundary_util import align_boundaries, boundaries, prf, sentence_words
from tests.golden_util import prose_only, words

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
MANIFEST = FIXTURES / "manifest.json"

if not MANIFEST.exists():
    pytest.skip(f"{MANIFEST} missing: fixture PDFs not added yet", allow_module_level=True)

NAMES = [e["name"] for e in json.loads(MANIFEST.read_text()) if e["class"] != "scanned"]


def _truth(name: str) -> list[str]:
    return (FIXTURES / f"{name}.sentences.txt").read_text().splitlines()


def _expected_prose(name: str) -> list[str]:
    path = FIXTURES / f"{name}.expected.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return prose_only((r["type"], r["text"]) for r in rows)[0]


@cache
def _measure(name: str) -> tuple[int, int, int, int, int]:
    """(tp, fp, fn, parser sentences, truth sentences) for one fixture."""
    truth = _truth(name)
    result = ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)
    block_type = {b.id: b.type for b in result.blocks}
    actual, _ = prose_only((block_type[s.block_id], s.text) for s in result.segments)
    tp, fp, fn = align_boundaries(
        sentence_words(actual), sentence_words(truth), boundaries(actual), boundaries(truth)
    )
    return tp, fp, fn, len(actual), len(truth)


def _row(name: str) -> str:
    tp, fp, fn, n_act, n_truth = _measure(name)
    p, r, f = prf(tp, fp, fn)
    return f"{name:34} {n_truth:6} {n_act:6} {tp:5} {fp:5} {fn:5} {p:7.4f} {r:7.4f} {f:7.4f}"


MIN_F1 = 0.90
MIN_RECALL = 0.97
MIN_MEAN_F1 = 0.95

HEADER = f"{'fixture':34} {'truth':>6} {'parser':>6} {'tp':>5} {'fp':>5} {'fn':>5} {'P':>7} {'R':>7} {'F1':>7}"


@pytest.mark.parametrize("name", NAMES)
def test_ing5_syn1_boundary_truth_keeps_expected_word_stream(name: str) -> None:
    truth = _truth(name)
    assert truth, f"{name}.sentences.txt is empty"
    assert all(line.strip() for line in truth), f"{name}.sentences.txt has a blank line"
    assert words(truth) == words(_expected_prose(name))


@pytest.mark.parametrize("name", NAMES)
def test_ing5_syn1_boundary_thresholds(name: str) -> None:
    tp, fp, fn, _, _ = _measure(name)
    p, r, f = prf(tp, fp, fn)
    print("\n" + HEADER + "\n" + _row(name))
    assert f >= MIN_F1, f"{name}: boundary F1 {f:.4f} < {MIN_F1} (P {p:.4f}, R {r:.4f})"
    assert r >= MIN_RECALL, (
        f"{name}: boundary recall {r:.4f} < {MIN_RECALL} (P {p:.4f}, F1 {f:.4f})"
    )


def test_ing5_syn1_boundary_mean_f1_table() -> None:
    scores = [prf(*_measure(n)[:3]) for n in NAMES]
    lines = [HEADER] + [_row(n) for n in NAMES]
    mean = [sum(s[k] for s in scores) / len(scores) for k in range(3)]
    label = f"mean ({len(NAMES)} fixtures)"
    lines.append(f"{label:34} {'':30} " + " ".join(f"{v:7.4f}" for v in mean))
    print("\nsentence-boundary P/R/F1, parser vs reviewed truth\n" + "\n".join(lines))
    assert mean[2] >= MIN_MEAN_F1, f"mean boundary F1 {mean[2]:.4f} < {MIN_MEAN_F1}"
