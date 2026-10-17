"""EVAL-4 Speech form: does the text we send to the voice read aloud correctly? (ING-6, ING-7,
SYN-4; D31)

Dataset: ``evals/data/speech_form.jsonl``, one pair per line: ``id``, ``category``, ``text``
(as written in a document), ``expected`` (how a careful narrator reads it aloud, authored from
the PRD rules, not from the normalizer's output), optional ``note`` and optional ``block``
(``heading``, ``table`` or ``equation``; default ``body``). A table's ``text`` is one row per
line with cells separated by `` | ``.

``spoken(text, block)`` produces the text the app hands the voice, through the app's own
functions in the order the app applies them:

1. ingestion (``hearnarro.ingestion.merge.merge_blocks`` then
   ``hearnarro.ingestion.segment.split_sentences``, which calls
   ``hearnarro.ingestion.normalize.normalize`` and builds the ING-7 table and equation cues);
   the document's acronym definitions come from ``hearnarro.ingestion.acronyms
   .document_definitions`` over the merged block texts, as ``ingest()`` does;
2. per segment ``normalized_text``, the backend's all-caps step
   (``hearnarro.synthesis.acronyms.caps_fold_spans``), then for every remaining all-caps token
   ``hearnarro.synthesis.acronyms.decide`` (with ``split_suffix`` and
   ``hearnarro.synthesis.lexicon_overrides.lookup``), mirroring
   ``KokoroBackend._tokens`` / ``_pronounce_acronyms``. A spelled token is rendered as its
   letters separated by spaces ("P D F"), a spoken one is left as written.

The voice front-end (D15, SYN-4): the scored text then goes through the backend's own
text-to-phoneme step, ``hearnarro.synthesis.kokoro_backend.build_g2p`` (misaki G2P with the
num2words shim, ``lexicon_overrides`` in the gold lexicon and the ``_OOVFallback``; no model
weights), and so does ``expected``. Digits the normalizer leaves are expanded by misaki, as the
listener hears them. Not modelled: the backend's post-G2P acronym re-read on phonemes (the
spell-out is applied as text in step 2 instead) and ``in_lexicon`` (false, so rule 4 of
``decide`` never fires and the heuristic decides).

Score per pair: ``exact`` = the phoneme tokens of ``actual`` and ``expected`` are equal
(in-word hyphens as spaces on both sides, whitespace collapsed, punctuation removed,
punctuation-only tokens dropped; stress marks kept); ``partial`` =
1 - phoneme-token edit distance / expected tokens, floored at 0; ``score`` = ``partial``. The
word-level text comparison is kept as ``text_exact`` / ``text_partial`` (canonical forms: lower
case, hyphens as spaces, punctuation other than in-word apostrophes removed). If misaki cannot
be imported every pair is skipped with the reason instead of scored.
"""

from __future__ import annotations

import json
import logging
import re
from functools import cache
from pathlib import Path
from typing import Any

from hearnarro.evals.scorers import seq_levenshtein

ID = "EVAL-4"
TITLE = "Speech form"
TIER = 0
DIRECTION = "higher"

DATA = Path(__file__).resolve().parents[1] / "data" / "speech_form.jsonl"
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
_CELL_X = (72.0, 232.0, 392.0, 552.0, 712.0, 872.0)
_CELL_W = 90.0


@cache
def load_pairs() -> tuple[dict[str, Any], ...]:
    """Every pair of the dataset, in file order."""
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())


def _blocks(text: str, block: str) -> list[Any]:
    from hearnarro.ingestion.models import BBox, Block, Line, Span

    lines: list[Line] = []
    for i, row in enumerate(text.split("\n")):
        top = 200.0 + 14.0 * i
        cells = row.split(" | ") if block == "table" else [row]
        width = _CELL_W if block == "table" else 468.0
        spans = [
            Span(c, BBox(_CELL_X[k], top, _CELL_X[k] + width, top + 12.0), "Helvetica", 10.0)
            for k, c in enumerate(cells)
        ]
        lines.append(Line(spans, BBox(spans[0].bbox.x0, top, spans[-1].bbox.x1, top + 12.0)))
    box = BBox(
        min(ln.bbox.x0 for ln in lines),
        lines[0].bbox.y0,
        max(ln.bbox.x1 for ln in lines),
        lines[-1].bbox.y1,
    )
    return [Block(page=0, index=0, bbox=box, lines=lines, type=block)]  # type: ignore[arg-type]


def _voice_text(text: str, definitions: dict[str, str]) -> str:
    """The backend's all-caps handling on one segment, rendered as text (module docstring)."""
    from hearnarro.synthesis import lexicon_overrides
    from hearnarro.synthesis.acronyms import caps_fold_spans, decide, is_acronym, split_suffix

    folded = caps_fold_spans(text, definitions)
    words = list(_WORD.finditer(text))
    out, pos = [], 0
    for i, m in enumerate(words):
        tok = m.group()
        word, suffix = (tok, "") if is_acronym(tok) else split_suffix(tok) or ("", "")
        if (
            not word
            or any(a < m.end() and m.start() < b for a, b in folded)
            or lexicon_overrides.lookup(tok)
            or lexicon_overrides.lookup(word)
        ):
            continue
        nxt = None
        if i + 1 < len(words) and text[m.end() : words[i + 1].start()].isspace():
            nxt = words[i + 1].group()
        if decide(word, next_word=nxt, definitions=definitions).spoken:
            continue
        out.append(text[pos : m.start()])
        out.append(" ".join(word[:-1]) + (" " if len(word) > 1 else "") + word[-1] + suffix)
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def spoken(text: str, block: str | None = None) -> str:
    """The text the app sends to the voice for ``text`` in a block of type ``block``."""
    from hearnarro.ingestion.acronyms import document_definitions
    from hearnarro.ingestion.merge import merge_blocks
    from hearnarro.ingestion.segment import split_sentences

    logical = merge_blocks(_blocks(text, block or "body"))
    definitions = document_definitions(b.text for b in logical)
    segments = []
    for lb in logical:
        segments.extend(
            split_sentences(lb, document_id=0, order_start=len(segments), id_start=len(segments))
        )
    return " ".join(_voice_text(s.normalized_text, definitions) for s in segments)


def canonical(text: str) -> list[str]:
    """Words for comparison: lower case, hyphens and dashes as spaces, other punctuation gone."""
    text = re.sub(r"[-–—]", " ", text.lower().replace("’", "'"))
    text = re.sub(r"(?<![a-z])'|'(?![a-z])", " ", text)
    return re.sub(r"[^\w\s']", " ", text).split()


_PUNCT = set(";:,.!?¡¿—–-…\"«»“”()[]{}'’")


@cache
def _g2p() -> Any:
    """The backend's US-English G2P front-end (no weights) with OOV warnings silenced."""
    from hearnarro.synthesis import kokoro_backend

    logging.getLogger(kokoro_backend.__name__).setLevel(logging.ERROR)
    return kokoro_backend.build_g2p(False, kokoro_backend.model_vocab())


def unavailable() -> str | None:
    """Why the G2P front-end cannot be built here, or None."""
    try:
        _g2p()
    except Exception as e:  # noqa: BLE001 - any import/download failure means skip
        return f"voice front-end unavailable: {type(e).__name__}: {e}"
    return None


def phonemes(text: str) -> list[str]:
    """Phoneme tokens of ``text`` through the backend's G2P, punctuation removed. In-word
    hyphens become spaces first, on both sides, as in ``canonical``: misaki gives a hyphenated
    compound ("eighty-four") one token with compound stress, while its own number reading
    yields separate words, so the hyphen would count as a phoneme difference."""
    _, tokens = _g2p()(re.sub(r"(?<=\w)-(?=\w)", " ", text))
    out = []
    for t in tokens:
        for piece in (t.phonemes or "").split():
            piece = "".join(c for c in piece if c not in _PUNCT)
            if piece:
                out.append(piece)
    return out


def dataset() -> list[dict[str, Any]]:
    """One example per pair; all skipped with the reason if misaki is unavailable."""
    reason = unavailable()
    return [dict(p, **{"class": p["category"], "skip": reason}) for p in load_pairs()]


def score(example: dict[str, Any]) -> dict[str, Any]:
    """id, class, exact, partial (= score), actual, actual_ph, expected_ph, text_exact,
    text_partial."""
    actual = spoken(example["text"], example.get("block"))
    got, want = canonical(actual), canonical(example["expected"])
    text_partial = max(0.0, 1 - seq_levenshtein(got, want) / max(1, len(want)))
    got_ph, want_ph = phonemes(actual), phonemes(example["expected"])
    partial = max(0.0, 1 - seq_levenshtein(got_ph, want_ph) / max(1, len(want_ph)))
    return {
        "id": example["id"],
        "class": example["class"],
        "exact": got_ph == want_ph,
        "partial": partial,
        "score": partial,
        "actual": actual,
        "actual_ph": " ".join(got_ph),
        "expected_ph": " ".join(want_ph),
        "text_exact": got == want,
        "text_partial": text_partial,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Phoneme exact-match accuracy overall and per category, mean partial credit, and the
    word-level text accuracy and partial mean alongside."""
    if not scores:
        return {"accuracy": 0.0, "partial_mean": 0.0, "by_category": {}}
    cats: dict[str, list[bool]] = {}
    for s in scores:
        cats.setdefault(s["class"], []).append(s["exact"])
    return {
        "accuracy": sum(s["exact"] for s in scores) / len(scores),
        "partial_mean": sum(s["partial"] for s in scores) / len(scores),
        "by_category": {c: sum(v) / len(v) for c, v in sorted(cats.items())},
        "text_accuracy": sum(s["text_exact"] for s in scores) / len(scores),
        "text_partial_mean": sum(s["text_partial"] for s in scores) / len(scores),
    }
