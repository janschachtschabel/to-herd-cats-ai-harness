"""Every module that registers outbox handlers. Importing this module registers them
all in `registry.REGISTRY`; the worker does so before it starts (`main.py`)."""

import app.modules.agents.hooks  # noqa: F401 -- what messaging asks of agents (runs, names)
import app.modules.automations.handlers  # noqa: F401 -- automation_events (event rules)
import app.modules.messaging.handlers  # noqa: F401 -- notify_on_message, publish_live, page_timeline
import app.modules.proposals.handlers  # noqa: F401 -- proposal_timeline, notify_on_proposal
import app.modules.skills.proposal_handlers  # noqa: F401 -- notify_on_skill_proposal
import app.modules.tickets.handlers  # noqa: F401 -- ticket_timeline, notify_on_ticket
import app.modules.wiki.review_handlers  # noqa: F401 -- notify_on_review_due
