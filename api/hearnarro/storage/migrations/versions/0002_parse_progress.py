"""Parse progress and duration on documents: pages_done, parse_ms (ING-1).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite supports ADD COLUMN directly; batch mode is only needed for drops/alters.
    op.execute("ALTER TABLE documents ADD COLUMN pages_done INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE documents ADD COLUMN parse_ms INTEGER")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("parse_ms")
        batch.drop_column("pages_done")
