"""Who a write is written for (`core/authorship.py`): an agent's run writes pages with
the person's rights, but the version (`author_*`, `run_id`) and the page's `created_by`
or `updated_by` carry the agent; an accepted proposal carries its author, while the
moderator who accepted it is the actor."""

from app.core.authorship import Authorship

__all__ = ["Authorship"]
