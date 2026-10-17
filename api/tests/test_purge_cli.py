"""``hearnarro purge-audio``: delete matching ``audio_cache`` rows and their files, print the
count (D19 A/B measurements; cost review 2, action 4).

Contract: ``_agent/specs/m4-library-interfaces.md`` section 1:
``hearnarro purge-audio --document-id N [--segment-id S] [--voice V] [--speed X]``.
``--data-dir`` is passed as for ``renormalize`` (``test_syn1_renormalize_cli.py``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hearnarro.cli import main
from hearnarro.storage.db import connect_sync, db_path, pack_char_map, run_migrations

# (voice, speed) cached for every segment of both documents
VARIANTS = [("af_heart", 1.0), ("af_heart", 1.5), ("am_adam", 1.0)]
SEGMENTS_PER_DOC = 3


def _path(doc: int, seg: int, voice: str, speed: float) -> str:
    return f"audio/{doc}/{seg}/{voice}_{speed:.2f}.webm"


def _seed(data_dir: Path) -> None:
    run_migrations(data_dir)
    with connect_sync(db_path(data_dir)) as conn:
        for doc in (1, 2):
            conn.execute(
                "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
                "VALUES (?, 't', 'f.pdf', ?, 'ready', '2026-10-17')",
                (doc, f"sha{doc}"),
            )
            for i in range(SEGMENTS_PER_DOC):
                seg_id = doc * 100 + i
                conn.execute(
                    'INSERT INTO blocks (id, document_id, page, "order", type, merged_text) '
                    "VALUES (?, ?, 1, ?, 'body', 'Some words.')",
                    (seg_id, doc, i),
                )
                conn.execute(
                    'INSERT INTO segments (id, document_id, block_id, "order", text, '
                    "normalized_text, char_start, char_end, char_map) "
                    "VALUES (?, ?, ?, ?, 'Some words.', 'Some words.', 0, 11, ?)",
                    (seg_id, doc, seg_id, i, pack_char_map(list(range(11)))),
                )
                for voice, speed in VARIANTS:
                    rel = _path(doc, seg_id, voice, speed)
                    f = data_dir / rel
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_bytes(b"x")
                    conn.execute(
                        "INSERT INTO audio_cache (segment_id, voice_id, speed, backend, "
                        "status, path, created_at) VALUES (?, ?, ?, 'kokoro', 'ready', ?, 'x')",
                        (seg_id, voice, speed, rel),
                    )


def _cached(data_dir: Path) -> set[tuple[int, str, float]]:
    with connect_sync(db_path(data_dir)) as conn:
        q = "SELECT segment_id, voice_id, speed FROM audio_cache"
        return {(r[0], r[1], r[2]) for r in conn.execute(q)}


def _files(data_dir: Path) -> set[str]:
    return {p.relative_to(data_dir).as_posix() for p in (data_dir / "audio").rglob("*.webm")}


def _count(out: str) -> int:
    nums = re.findall(r"\d+", out)
    assert nums, out
    return int(nums[-1])


def _purge(data_dir: Path, *args: str) -> list[str]:
    return ["purge-audio", "--data-dir", str(data_dir), *args]


def test_d19_purge_audio_whole_document(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    assert main(_purge(tmp_path, "--document-id", "1")) == 0
    assert _count(capsys.readouterr().out) == SEGMENTS_PER_DOC * len(VARIANTS)
    assert {c[0] // 100 for c in _cached(tmp_path)} == {2}
    assert all(f.startswith("audio/2/") for f in _files(tmp_path))
    assert len(_files(tmp_path)) == SEGMENTS_PER_DOC * len(VARIANTS)
    # D19: emptied directories are removed, others stay
    assert not (tmp_path / "audio" / "1").exists()
    assert (tmp_path / "audio" / "2" / "200").is_dir()


def test_d19_purge_audio_filters_segment_voice_speed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    args = ["--document-id", "1", "--segment-id", "101", "--voice", "af_heart", "--speed", "1.5"]
    assert main(_purge(tmp_path, *args)) == 0
    assert _count(capsys.readouterr().out) == 1
    assert (101, "af_heart", 1.5) not in _cached(tmp_path)
    assert len(_cached(tmp_path)) == 2 * SEGMENTS_PER_DOC * len(VARIANTS) - 1
    assert _path(1, 101, "af_heart", 1.5) not in _files(tmp_path)
    assert _path(1, 101, "af_heart", 1.0) in _files(tmp_path)
    assert (tmp_path / "audio" / "1" / "101").is_dir()

    assert main(_purge(tmp_path, "--document-id", "1", "--voice", "am_adam")) == 0
    assert _count(capsys.readouterr().out) == SEGMENTS_PER_DOC
    assert not any(c[1] == "am_adam" and c[0] // 100 == 1 for c in _cached(tmp_path))
    assert _path(2, 200, "am_adam", 1.0) in _files(tmp_path)


def test_d19_purge_audio_no_match_prints_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    assert main(_purge(tmp_path, "--document-id", "1", "--voice", "nobody")) == 0
    assert _count(capsys.readouterr().out) == 0
    assert len(_cached(tmp_path)) == 2 * SEGMENTS_PER_DOC * len(VARIANTS)
