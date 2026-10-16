"""Initial schema: the D7 DDL verbatim (ING-1; documents, blocks, sections, segments,
audio_cache, settings).

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Copied from docs/TECHNICAL_DESIGN.md "Storage (D7)"; keep in sync with that block.
DDL = [
    """
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,            -- dedupe re-uploads
  page_count INTEGER,
  status TEXT NOT NULL CHECK (status IN ('uploaded','parsing','ready','failed')),
  fail_reason TEXT,
  voice_id TEXT, speed REAL,              -- per-document settings, NULL = use global
  position_segment_id INTEGER, position_offset_ms INTEGER DEFAULT 0,
  created_at TEXT NOT NULL, last_opened_at TEXT
)""",
    """
CREATE TABLE blocks (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page INTEGER NOT NULL, "order" INTEGER NOT NULL,
  type TEXT NOT NULL,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL,
  merged_text TEXT NOT NULL
)""",
    """
CREATE TABLE sections (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  title TEXT NOT NULL, level INTEGER NOT NULL, first_segment_id INTEGER
)""",
    """
CREATE TABLE segments (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  block_id INTEGER NOT NULL REFERENCES blocks(id),
  section_id INTEGER REFERENCES sections(id),
  "order" INTEGER NOT NULL,
  text TEXT NOT NULL, normalized_text TEXT NOT NULL,
  char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
  char_map BLOB NOT NULL                  -- packed uint16 array
)""",
    'CREATE UNIQUE INDEX segments_doc_order ON segments(document_id, "order")',
    """
CREATE TABLE audio_cache (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  voice_id TEXT NOT NULL, speed REAL NOT NULL, backend TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ready','failed')),
  path TEXT, duration_ms INTEGER, timestamps_json TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (segment_id, voice_id, speed, backend)
)""",
    "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
]


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)


def downgrade() -> None:
    for name in ("settings", "audio_cache", "segments", "sections", "blocks", "documents"):
        op.execute(f"DROP TABLE {name}")
