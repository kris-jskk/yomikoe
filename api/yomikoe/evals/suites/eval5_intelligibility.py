"""EVAL-5 Intelligibility: can the audio be understood? (SYN-1, SYN-4; D31, D34)

Round trip: the sentence's normalized text (what the app sends the voice) is synthesized by
Kokoro through the service's trim/stretch path (``_voice.render``), transcribed by the pinned
faster-whisper recogniser (``_asr``), and scored by word error rate against the input.

Dataset: ``data/sentences_50.jsonl``, 50 fixture sentences chosen by the bench rule
(``scripts/bench.py``: body/list rows of 80..200 characters from
``tests/fixtures/pdfs/*.expected.jsonl``, normalized, distinct), then a seeded sample
(``SEED``) so the list is deterministic; ``select_sentences()`` regenerates it. Each sentence
runs in two voices (one female, one male, ``VOICES``) at every speed in ``SPEEDS``.

WER per example = (substitutions + deletions + insertions) / reference words, from the word
edit distance (``scorers.seq_levenshtein``); both sides lower-cased, hyphens and dashes split,
punctuation stripped from each token (``norm_words``). Lower is better.
"""

from __future__ import annotations

import json
import random
import re
from functools import cache
from pathlib import Path
from typing import Any

from yomikoe.evals.scorers import seq_levenshtein, words
from yomikoe.evals.suites import _asr, _voice

ID = "EVAL-5"
TITLE = "Intelligibility"
TIER = 1
DIRECTION = "lower"
# D33: per-metric rules for compare: (direction, tolerance, relative); "none" is not compared.
METRIC_RULES: dict[str, tuple[str, float, bool]] = {"speed": ("none", 0.0, False)}

VOICES = ("af_heart", "am_michael")  # female, male (US English)
SPEEDS = (1.0, 2.0, 3.0)  # 0.5 left out: the full run would pass 15 min (E2 brief)
SEED = 34
N_SENTENCES = 50
API = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parents[1] / "data" / "sentences_50.jsonl"


def select_sentences(n: int = N_SENTENCES, seed: int = SEED) -> list[dict[str, str]]:
    """The bench rule over every fixture, then ``random.Random(seed).sample``, in pool order."""
    from yomikoe.ingestion.normalize import normalize

    pool: list[dict[str, str]] = []
    seen: set[str] = set()
    for f in sorted((API / "tests" / "fixtures" / "pdfs").glob("*.expected.jsonl")):
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        for k, r in enumerate(rows):
            if r["type"] in ("body", "list") and 80 <= len(r["text"]) <= 200:
                text = normalize(r["text"])[0]
                if text not in seen:
                    seen.add(text)
                    pool.append({"id": f"{f.name.split('.')[0]}#{k}", "text": text})
    picks = sorted(random.Random(seed).sample(range(len(pool)), n))
    return [pool[i] for i in picks]


@cache
def load_sentences() -> tuple[dict[str, str], ...]:
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())


def norm_words(text: str) -> list[str]:
    """Lower case, hyphens/dashes/slashes as spaces, punctuation stripped per token (D14)."""
    return words([re.sub(r"[-‐‑–—/]", " ", text.replace("’", "'"))])


def wer(reference: list[str], hypothesis: list[str]) -> float:
    return seq_levenshtein(hypothesis, reference) / max(1, len(reference))


def unavailable() -> str | None:
    return _voice.unavailable() or _asr.unavailable()


def dataset(
    limit: int | None = None,
    speeds: tuple[float, ...] | None = None,
    voices: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """One example per sentence × voice × speed (all skipped with the reason if unavailable)."""
    reason = unavailable()
    return [
        {
            "id": f"{s['id']}@{v}@{sp}",
            "class": str(sp),
            "sentence_id": s["id"],
            "text": s["text"],
            "voice": v,
            "speed": sp,
            "skip": reason,
        }
        for sp in speeds or SPEEDS
        for v in voices or VOICES
        for s in load_sentences()[:limit]
    ]


def score(example: dict[str, Any]) -> dict[str, Any]:
    rt = _voice.roundtrip(example["text"], example["voice"], example["speed"])
    ref = norm_words(example["text"])
    hyp = norm_words(" ".join(w.word for w in rt.asr))
    value = wer(ref, hyp)
    return {
        "id": example["id"],
        "class": example["class"],
        "sentence_id": example["sentence_id"],
        "speed": example["speed"],
        "voice": example["voice"],
        "reference": " ".join(ref),
        "hypothesis": " ".join(hyp),
        "wer": value,
        "score": value,
        "direction": DIRECTION,
    }


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean WER, the worst example, and mean WER per voice and per speed."""
    if not scores:
        return {"mean_wer": 0.0, "per_voice": {}, "per_speed": {}}
    worst = max(scores, key=lambda s: s["wer"])
    by_voice: dict[str, list[float]] = {}
    by_speed: dict[str, list[float]] = {}
    for s in scores:
        by_voice.setdefault(s["voice"], []).append(s["wer"])
        by_speed.setdefault(str(s["speed"]), []).append(s["wer"])
    return {
        "mean_wer": _mean([s["wer"] for s in scores]),
        "worst": {k: worst[k] for k in ("id", "wer", "reference", "hypothesis")},
        "per_voice": {k: _mean(v) for k, v in sorted(by_voice.items())},
        "per_speed": {
            k: _mean(v) for k, v in sorted(by_speed.items(), key=lambda kv: float(kv[0]))
        },
    }
