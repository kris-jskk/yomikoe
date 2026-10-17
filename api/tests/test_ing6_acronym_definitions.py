"""ING-6: ingestion records acronym definitions per document (``documents.acronyms_json``,
migration 0003) and GET /documents/{id} returns them as ``acronyms``."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hearnarro.ingestion.acronyms import find_definitions


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We use a Transferable Erosion Deposit (TED) model.", {"TED": "Transferable Erosion Deposit"}),
        ("The Zero Trust Architecture (ZTA) is new.", {"ZTA": "Zero Trust Architecture"}),
        ("The ZTA (Zero Trust Architecture) is new.", {"ZTA": "Zero Trust Architecture"}),
        ("the Department of Energy (DOE) said", {"DOE": "Department of Energy"}),
        ("See Figure 2 (left) and Table 3 (right).", {}),
        ("A TED (left) panel.", {}),
        ("the Erosion Deposit (TED) only", {}),  # initials do not match
        ("with (TED) alone", {}),
    ],
)  # fmt: skip
def test_ing6_find_definitions(text: str, expected: dict[str, str]) -> None:
    assert find_definitions(text) == expected


def test_ing6_first_definition_wins() -> None:
    text = "A Transferable Erosion Deposit (TED). Later, TED (Total Erosion Depth) again."
    assert find_definitions(text) == {"TED": "Transferable Erosion Deposit"}


def _alembic_cfg(db: Path):
    from alembic.config import Config

    from hearnarro.storage.db import MIGRATIONS_DIR, sync_url

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sync_url(db).replace("%", "%%"))
    return cfg


def _columns(db: Path) -> set[str]:
    with sqlite3.connect(db) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(documents)")}


def test_ing6_migration_0003_on_empty_db(tmp_path: Path) -> None:
    from hearnarro.storage.db import db_path, run_migrations

    run_migrations(tmp_path)
    assert "acronyms_json" in _columns(db_path(tmp_path))


def test_ing6_migration_0003_on_a_0002_db(tmp_path: Path) -> None:
    from alembic import command

    db = tmp_path / "hearnarro.db"
    command.upgrade(_alembic_cfg(db), "0002")
    assert "acronyms_json" not in _columns(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO documents (title, filename, sha256, status, created_at) "
            "VALUES ('t', 'f.pdf', 'abc', 'ready', '2026-10-16T00:00:00Z')"
        )
    command.upgrade(_alembic_cfg(db), "head")
    assert "acronyms_json" in _columns(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT title, acronyms_json FROM documents").fetchall() == [
            ("t", None)
        ]


def _pdf(lines: list[str]) -> bytes:
    body = ["BT /F1 18 Tf 72 720 Td (Erosion Notes) Tj ET"]
    for i, line in enumerate(lines):
        body.append(f"BT /F1 10 Tf 72 {690 - 14 * i} Td ({line}) Tj ET")
    stream = "\n".join(body).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objs) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


async def test_ing6_get_document_returns_acronym_definitions(tmp_path: Path) -> None:
    from tests.test_api_documents import client_for, upload, wait_settled

    lines = ["The Transferable Erosion Deposit \\(TED\\) is measured on every slope."]
    lines += ["This is an ordinary line of body text about TED values and rain."] * 11
    pdf = tmp_path / "erosion.pdf"
    pdf.write_bytes(_pdf(lines))
    async with client_for(tmp_path / "data") as client:
        resp = await upload(client, pdf)
        doc = await wait_settled(client, resp.json()["id"])
    assert doc["status"] == "ready", doc
    assert doc["acronyms"] == {"TED": "Transferable Erosion Deposit"}
