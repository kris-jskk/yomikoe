"""Pronunciation overrides: per-document and global (``document_id`` NULL) word -> respelling
(TERM-2).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE pronunciations (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NULL REFERENCES documents(id) ON DELETE CASCADE,
  word TEXT NOT NULL,
  respelling TEXT NOT NULL,
  created_at TEXT,
  UNIQUE (document_id, word)
)"""
    )
    # SQLite treats NULLs as distinct in UNIQUE, so the global lexicon needs its own index.
    op.execute(
        "CREATE UNIQUE INDEX ux_pronunciations_global_word ON pronunciations(word) "
        "WHERE document_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_pronunciations_global_word")
    op.execute("DROP TABLE pronunciations")
