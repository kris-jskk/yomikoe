"""EVAL-9 Listening sessions: prepare a rubric sheet, then ingest it once a person fills it in
(D31, D34; SYN-1).

``prepare`` renders the first ``N_SENTENCES`` of ``data/sentences_50.jsonl`` in each voice of
``VOICES`` (the EVAL-5 voices) as ``<sentence_id>__<voice>.wav`` and writes ``sheet.md``: a
header (date, commit, backend, listener left blank) and one blank table row per clip. The
listener follows ``data/listening_rubric.md``. ``ingest`` parses a filled sheet, validates
every row (naturalness and pacing ints 1..5, pron_errors int >= 0, listener named) and writes
the session record ``<out_dir>/<date>_<listener>.json`` (rows + per-voice and overall
aggregates), which the EVAL-9 suite reads.

``--source formula`` renders ``data/listening_formula_10.jsonl`` (the reader's spoken output for the
ten M5 formula fixtures, written by ``api/scripts/make_listening_formula.py``; MATH-1..4, M5 gate
clause d) instead of the general sentences; the sheet header records ``source`` and ``ingest``
copies it into the session json.

CLI (registered in ``__main__``): ``python -m yomikoe.evals listening prepare --out DIR
[--backend fake|kokoro] [--source general|formula]`` and ``python -m yomikoe.evals listening ingest SHEET.md [--out DIR]``.
"""

from __future__ import annotations

import argparse
import json
import re
import wave
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from yomikoe.evals.suites import eval5_intelligibility as e5

N_SENTENCES = 10
VOICES = e5.VOICES  # female, male
# Repo-root evals/listening/ (api/yomikoe/evals/listening.py -> parents[3] is the repo root).
LISTENING_DIR = Path(__file__).resolve().parents[3] / "evals" / "listening"
FORMULA_FILE = Path(__file__).resolve().parent / "data" / "listening_formula_10.jsonl"
SOURCES = ("general", "formula")
RUBRIC = Path(__file__).resolve().parent / "data" / "listening_rubric.md"
COLUMNS = ("clip", "sentence", "naturalness", "pacing", "pron_errors", "notes")
HEADER_KEYS = ("date", "commit", "backend", "source", "listener")
# The fake backend has no Kokoro voice ids; clips keep the real names (silence, for tests).
_FAKE_VOICE = {"af_heart": "fake_f1", "am_michael": "fake_m1"}
_PIPE = re.compile(r"(?<!\\)\|")


def _render_fn(backend: str) -> Callable[[str, str], Any]:
    """(text, voice) -> SynthResult for the named backend."""
    if backend == "fake":
        from yomikoe.synthesis.fake import FakeBackend

        fake = FakeBackend()
        return lambda text, voice: fake.synthesize(text, _FAKE_VOICE.get(voice, voice), 1.0)
    if backend == "kokoro":
        from yomikoe.evals.suites import _voice

        reason = _voice.unavailable()
        if reason:
            raise RuntimeError(reason)
        return lambda text, voice: _voice.render(text, voice, 1.0)
    raise ValueError(f"unknown backend {backend!r}: fake or kokoro")


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def load_source(source: str) -> list[dict[str, Any]]:
    """The first ``N_SENTENCES`` sentences ({id, text, ...}) of the named source."""
    if source == "general":
        return e5.load_sentences()[:N_SENTENCES]
    if source == "formula":
        lines = FORMULA_FILE.read_text(encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()][:N_SENTENCES]
    raise ValueError(f"unknown source {source!r}: {' or '.join(SOURCES)}")


def prepare(out_dir: Path, backend: str = "kokoro", source: str = "general") -> Path:
    """Render the 20 clips into ``out_dir`` and write ``out_dir/sheet.md``; return its path."""
    from yomikoe.evals.runner import _short_sha

    sentences = load_source(source)
    render = _render_fn(backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for voice in VOICES:
        for s in sentences:
            clip = f"{s['id']}__{voice}.wav"
            res = render(s["text"], voice)
            _write_wav(out_dir / clip, res.audio, res.sample_rate)
            rows.append(f"| {clip} | {_cell(s['text'])} |  |  |  |  |")
    lines = [
        "# YomiKoe listening sheet (EVAL-9)",
        "",
        f"- date: {datetime.now(UTC):%Y-%m-%d}",
        f"- commit: {_short_sha()}",
        f"- backend: {backend}",
        f"- source: {source}",
        "- listener: ",
        "",
        "Rubric: api/yomikoe/evals/data/listening_rubric.md. Fill every naturalness, pacing",
        "and pron_errors cell and your name above, then run",
        "`python -m yomikoe.evals listening ingest <this sheet>` from api/.",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
        *rows,
    ]
    sheet = out_dir / "sheet.md"
    sheet.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sheet


def parse_sheet(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    """(header, rows) of a sheet; cells are stripped strings, nothing is validated."""
    header: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- (\w+):(.*)$", line)
        if m and m.group(1) in HEADER_KEYS:
            header[m.group(1)] = m.group(2).strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in _PIPE.split(line.strip())[1:-1]]
        if cells[:1] == ["clip"] or all(set(c) <= set("-: ") for c in cells):
            continue  # the column header or the separator row
        if len(cells) != len(COLUMNS):
            raise ValueError(f"{path}: row has {len(cells)} cells, expected {len(COLUMNS)}")
        rows.append(dict(zip(COLUMNS, cells, strict=True)))
    return header, rows


def _int(value: str, field: str, clip: str, lo: int, hi: int | None) -> int:
    if not re.fullmatch(r"-?\d+", value):
        raise ValueError(f"{clip}: {field} must be an integer, got {value!r}")
    n = int(value)
    if n < lo or (hi is not None and n > hi):
        raise ValueError(f"{clip}: {field} {n} outside {lo}..{hi if hi is not None else 'inf'}")
    return n


def _mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mean_naturalness": _mean([r["naturalness"] for r in rows]),
        "mean_pacing": _mean([r["pacing"] for r in rows]),
        "pron_errors": sum(r["pron_errors"] for r in rows),
    }


def ingest(sheet: Path, out_dir: Path = LISTENING_DIR) -> tuple[dict[str, Any], Path]:
    """Validate a filled sheet and write ``<out_dir>/<date>_<listener>.json``; (session, path).

    Raises ``ValueError`` (and writes nothing) on a blank listener, a blank cell, a score
    outside 1..5 or a negative error count.
    """
    header, raw = parse_sheet(sheet)
    listener = header.get("listener", "")
    if not listener:
        raise ValueError(f"{sheet}: listener is blank")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", header.get("date", "")):
        raise ValueError(f"{sheet}: date must be YYYY-MM-DD")
    if not raw:
        raise ValueError(f"{sheet}: no rows")
    rows = []
    for r in raw:
        clip = r["clip"]
        if "__" not in clip or not clip.endswith(".wav"):
            raise ValueError(f"{clip}: clip must be <sentence_id>__<voice>.wav")
        sentence_id, voice = clip[: -len(".wav")].rsplit("__", 1)
        rows.append(
            {
                "clip": clip,
                "sentence_id": sentence_id,
                "voice": voice,
                "sentence": r["sentence"],
                "words": len(r["sentence"].split()),
                "naturalness": _int(r["naturalness"], "naturalness", clip, 1, 5),
                "pacing": _int(r["pacing"], "pacing", clip, 1, 5),
                "pron_errors": _int(r["pron_errors"], "pron_errors", clip, 0, None),
                "notes": r["notes"],
            }
        )
    by_voice: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_voice.setdefault(row["voice"], []).append(row)
    session = {
        "session_id": f"{header['date']}_{re.sub(r'[^A-Za-z0-9_-]+', '-', listener)}",
        **{k: header.get(k, "") for k in HEADER_KEYS if k != "source"},
        "source": header.get("source") or "general",
        "sheet": sheet.name,
        "rows": rows,
        "aggregates": {
            "per_voice": {v: _summary(rs) for v, rs in sorted(by_voice.items())},
            "overall": _summary(rows),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{session['session_id']}.json"
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return session, path


def register(sub: Any) -> None:
    """Add the ``listening`` subparser (verbs ``prepare`` and ``ingest``) to ``main``'s parser."""
    p_listen = sub.add_parser("listening", help="EVAL-9 listening sessions: prepare, ingest")
    verbs = p_listen.add_subparsers(dest="verb", required=True)
    p_prep = verbs.add_parser("prepare", help="render the clips and write a blank sheet")
    p_prep.add_argument("--out", required=True, help="directory for the clips and sheet.md")
    p_prep.add_argument("--backend", choices=("fake", "kokoro"), default="kokoro")
    p_prep.add_argument("--source", choices=SOURCES, default="general")
    p_ing = verbs.add_parser("ingest", help="validate a filled sheet and record the session")
    p_ing.add_argument("sheet", help="the filled sheet.md")
    p_ing.add_argument("--out", default=None, help="sessions directory (evals/listening/)")


def run_verb(args: argparse.Namespace) -> int:
    """Execute a parsed ``listening`` verb."""
    if args.verb == "prepare":
        sheet = prepare(Path(args.out), backend=args.backend, source=args.source)
        print(f"sheet: {sheet}\nclips: {len(list(sheet.parent.glob('*.wav')))}")
        return 0
    _, path = ingest(Path(args.sheet), Path(args.out) if args.out else LISTENING_DIR)
    print(f"session: {path}")
    return 0
