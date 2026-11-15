"""m7 page review (plan M7 task 6, decision 11): `space.review_interval_days` (NULL:
off) and `space.review_checked_on` (the UTC day the daily pass last went through the
space); `page.reviewed_at` (set on publishing and by "mark as reviewed") and
`page.review_notified_at` (when `page.review_due` was last emitted for it); the
notification reason `review_due`; indexes for the pass.

Expand only: nullable columns, a widened CHECK, new indexes. The backfill gives every
published page its publication time as its last review (`published_at`, else when it
was created), so turning an interval on does not make every page due at once unless
it really was published that long ago. The previous release never writes the new
columns or the reason; it reads a notification with reason `review_due` only once
this release wrote one (rolling update note, docs).

Revision ID: d4f6b8a0c2e4
Revises: f2a4c6e8b0d1
Create Date: 2026-11-14 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6b8a0c2e4"
down_revision: str | None = "f2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFY = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal',"
    " 'approval', 'question', 'run_stopped', 'skill_proposal', 'automation'"
)
LIVE_PUBLISHED = sa.text("trashed_at IS NULL AND status = 'published'")


def _replace_reason(reasons: str) -> None:
    op.drop_constraint(op.f("ck_notification_reason"), "notification", type_="check")
    op.create_check_constraint(
        op.f("ck_notification_reason"), "notification", f"reason IN ({reasons})"
    )


def upgrade() -> None:
    op.add_column("space", sa.Column("review_interval_days", sa.Integer(), nullable=True))
    op.add_column("space", sa.Column("review_checked_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_space_review_interval_days"),
        "space",
        "review_interval_days IS NULL OR review_interval_days BETWEEN 7 AND 730",
    )
    op.create_index(
        "ix_space_review_checked_on",
        "space",
        ["review_checked_on"],
        postgresql_where=sa.text("review_interval_days IS NOT NULL"),
    )
    op.add_column("page", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "page", sa.Column("review_notified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE page SET reviewed_at = COALESCE(published_at, created_at)"
        " WHERE status = 'published'"
    )
    op.create_index(
        "ix_page_space_id_reviewed_at",
        "page",
        ["space_id", "reviewed_at"],
        postgresql_where=LIVE_PUBLISHED,
    )
    _replace_reason(f"{NOTIFY}, 'review_due'")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE reason = 'review_due'")
    _replace_reason(NOTIFY)
    op.drop_index(
        "ix_page_space_id_reviewed_at", table_name="page", postgresql_where=LIVE_PUBLISHED
    )
    op.drop_column("page", "review_notified_at")
    op.drop_column("page", "reviewed_at")
    op.drop_index(
        "ix_space_review_checked_on",
        table_name="space",
        postgresql_where=sa.text("review_interval_days IS NOT NULL"),
    )
    op.drop_constraint(op.f("ck_space_review_interval_days"), "space", type_="check")
    op.drop_column("space", "review_checked_on")
    op.drop_column("space", "review_interval_days")
