"""``yomikoe renormalize``: rewrite a document's normalized_text/char_map and drop the
audio cache of the segments that changed (SYN-1 char_map consistency; PART II report)."""

from pathlib import Path

import pytest

from yomikoe.cli import main
from yomikoe.ingestion.normalize import normalize
from yomikoe.storage.db import connect_sync, db_path, pack_char_map, run_migrations

ROWS = [  # (block type, text, stale normalized_text)
    ("heading", "PART II", "PART II"),
    ("body", "We read Chapter IV twice.", "We read Chapter IV twice."),
    ("body", "Plain prose stays put.", "Plain prose stays put."),
    ("heading", "III", "III"),
]


def _seed(data_dir: Path) -> None:
    run_migrations(data_dir)
    orphan = data_dir / "audio" / "1" / "100" / "af_heart_1.00.webm"  # one file on disk
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"x")
    with connect_sync(db_path(data_dir)) as conn:
        for doc in (1, 2):
            conn.execute(
                "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
                "VALUES (?, 't', 'f.pdf', ?, 'ready', '2026-10-17')",
                (doc, f"sha{doc}"),
            )
            for i, (btype, text, stale) in enumerate(ROWS):
                seg_id = doc * 100 + i
                conn.execute(
                    'INSERT INTO blocks (id, document_id, page, "order", type, merged_text) '
                    "VALUES (?, ?, 1, ?, ?, ?)",
                    (seg_id, doc, i, btype, text),
                )
                conn.execute(
                    'INSERT INTO segments (id, document_id, block_id, "order", text, '
                    "normalized_text, char_start, char_end, char_map) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                    (
                        seg_id,
                        doc,
                        seg_id,
                        i,
                        text,
                        stale,
                        len(text),
                        pack_char_map(list(range(len(stale)))),
                    ),
                )
                conn.execute(
                    "INSERT INTO audio_cache (segment_id, voice_id, speed, backend, status, "
                    "path, created_at) VALUES (?, 'af_heart', 1.0, 'kokoro', 'ready', ?, 'x')",
                    (seg_id, f"audio/{doc}/{seg_id}/af_heart_1.00.webm"),
                )


def _rows(data_dir: Path, doc: int) -> dict[int, str]:
    with connect_sync(db_path(data_dir)) as conn:
        q = "SELECT id, normalized_text FROM segments WHERE document_id = ?"
        return dict(conn.execute(q, (doc,)).fetchall())


def _cached(data_dir: Path) -> set[int]:
    with connect_sync(db_path(data_dir)) as conn:
        return {r[0] for r in conn.execute("SELECT segment_id FROM audio_cache")}


def test_syn1_renormalize_document(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    assert main(["renormalize", "--data-dir", str(tmp_path), "--document-id", "1"]) == 0
    out = capsys.readouterr().out
    assert "segments changed: 3" in out
    assert "cache rows removed: 3" in out
    assert "orphaned audio files left on disk: 1" in out
    assert _rows(tmp_path, 1) == {
        100: "Part two",
        101: "We read Chapter four twice.",
        102: "Plain prose stays put.",
        103: "three",
    }
    assert _rows(tmp_path, 2)[200] == "PART II"  # other document untouched
    assert _cached(tmp_path) == {102, 200, 201, 202, 203}
    with connect_sync(db_path(tmp_path)) as conn:
        blob = conn.execute("SELECT char_map FROM segments WHERE id = 100").fetchone()[0]
    from yomikoe.storage.db import unpack_char_map

    assert unpack_char_map(blob) == normalize("PART II", heading=True)[1]
    # Idempotent: a second run changes nothing.
    assert main(["renormalize", "--data-dir", str(tmp_path), "--document-id", "1"]) == 0
    out = capsys.readouterr().out
    assert "segments changed: 0" in out
    assert "cache rows removed: 0" in out


def test_syn1_renormalize_all(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    assert main(["renormalize", "--data-dir", str(tmp_path), "--all"]) == 0
    assert "segments changed: 6" in capsys.readouterr().out
    assert _rows(tmp_path, 2)[200] == "Part two"
    assert _cached(tmp_path) == {102, 202}


def test_ing11_renormalize_profile_and_math_json_reproduce_ingestion(tmp_path: Path) -> None:
    """ING-11, D40, MATH-1..4: renormalize re-speaks each segment from its stored ``math_json``
    under the stored profile, so a stale row comes back to exactly what ``ingest()`` wrote."""
    from yomikoe.cli import renormalize_document
    from yomikoe.evals.suites import _fixtures
    from yomikoe.storage.db import unpack_char_map
    from yomikoe.storage.jobs import _write_result

    result = _fixtures.ingest_result("formula_01_pfn_bayes")
    run_migrations(tmp_path)
    with connect_sync(db_path(tmp_path)) as conn:
        conn.execute(
            "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
            "VALUES (1, 't', 'f.pdf', 'sha1', 'parsing', '2026-10-17')"
        )
        _write_result(conn, 1, result, None, 0)
        q = 'SELECT "order", normalized_text, char_map, math_json FROM segments ORDER BY "order"'
        assert sum(1 for r in conn.execute(q) if r[3]) > 0  # math_json persisted
        assert renormalize_document(conn, 1, tmp_path) == (0, 0, 0)  # already reproduces
        with conn:
            conn.execute("UPDATE segments SET normalized_text = 'stale', char_map = ?", (b"",))
        changed, _, _ = renormalize_document(conn, 1, tmp_path)
        rows = conn.execute(q).fetchall()
    assert changed == len(result.segments)
    want = sorted(result.segments, key=lambda s: s.order)
    assert [(r[1], unpack_char_map(r[2])) for r in rows] == [
        (s.normalized_text, s.char_map) for s in want
    ]
