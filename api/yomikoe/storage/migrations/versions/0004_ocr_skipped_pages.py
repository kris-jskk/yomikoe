"""Pages left empty for want of an OCR engine: documents.ocr_skipped_pages (ING-2, D28).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0 when every page had text or OCR ran; NULL for documents ingested before 0004.
    op.execute("ALTER TABLE documents ADD COLUMN ocr_skipped_pages INTEGER")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("ocr_skipped_pages")
