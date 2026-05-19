"""add product export exclusion flag

Revision ID: 0006_product_export_exclusion
Revises: 0005_product_conversion_multiplier
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_product_export_exclusion"
down_revision = "0005_product_conversion_multiplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "exclude_from_export",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("products", "exclude_from_export", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "exclude_from_export")
