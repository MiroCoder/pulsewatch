"""initial schema

Revision ID: 37fb9a6f164d
Revises: 
Create Date: 2026-10-29 17:50:49.510874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37fb9a6f164d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "monitors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable = False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
    )

    op.create_table(
        "check_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monitor_id", sa.Integer(), sa.ForeignKey("monitors.id"), nullable = False),
        sa.Column("status_code", sa.Integer(), nullable = True),
        sa.Column("latency_ms", sa.Float(), nullable = True),
        sa.Column("error", sa.String(), nullable = True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable = False),
    )

def downgrade():
    op.drop_table("check_results")
    op.drop_table("monitors")