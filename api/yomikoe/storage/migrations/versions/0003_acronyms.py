"""Acronym definitions found at ingestion: documents.acronyms_json (ING-6).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JSON object {ACR: expansion}; NULL for documents ingested before 0003.
    op.execute("ALTER TABLE documents ADD COLUMN acronyms_json TEXT")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("acronyms_json")
