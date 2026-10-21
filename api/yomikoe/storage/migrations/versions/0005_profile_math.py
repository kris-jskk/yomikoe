"""Document profile and per-segment maths: documents.profile_json, segments.math_json (ING-11,
D40; MATH-1..4).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL for documents ingested before 0005: read as PROSE_DEFAULT (today's rules).
    op.execute("ALTER TABLE documents ADD COLUMN profile_json TEXT")
    # Phase 3 (MATH-1..4) writes it; NULL means the segment has no maths.
    op.execute("ALTER TABLE segments ADD COLUMN math_json TEXT")


def downgrade() -> None:
    with op.batch_alter_table("segments") as batch:
        batch.drop_column("math_json")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("profile_json")
