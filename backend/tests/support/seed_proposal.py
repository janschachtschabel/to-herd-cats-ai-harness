"""An agent's page proposal for the browser tests and screenshots (plan M6 task 11).

Proposals have no public route (people do not propose in M6; agents propose through
a tool of their run), so the browser tests make one through the service the tool will
call: as the run of `--agent` that the person `--email` asked for, held to the agent's
own roles (`agents.actor.run_actor`). The database is `HERD_DATABASE_URL`'s. Prints
the proposal as JSON (`id`, `version`).

    uv run --no-sync python -m tests.support.seed_proposal --email anna@e2e.example \
        --agent <agent id> --page <page id> --content "New text" --reason "Why"
    ... --space <space id> --title "New page" --content "Text" --reason "Why"
"""

import argparse
import asyncio
import json
import uuid

from sqlalchemy import select

import app.models_registry  # noqa: F401 (every table, for the foreign keys)
from app.core.db import Database
from app.core.principal import Principal
from app.modules.agents.actor import run_actor
from app.modules.proposals.service import ProposalService
from app.modules.users.models import User


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="the person who asked the agent")
    parser.add_argument("--agent", required=True, type=uuid.UUID)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--page", type=uuid.UUID, help="propose a change of this page")
    target.add_argument("--space", type=uuid.UUID, help="propose a new page in this space")
    parser.add_argument("--title", help="the new page's title (with --space)")
    parser.add_argument("--content", required=True)
    parser.add_argument("--reason", required=True)
    return parser.parse_args()


async def seed(args: argparse.Namespace) -> dict[str, object]:
    database = Database()
    try:
        async with database.session_factory() as session:
            user = await session.scalar(select(User).where(User.email == args.email))
            if user is None:
                raise SystemExit(f"no person {args.email}")
            actor = await run_actor(session, user.org_id, user.id, args.agent)
            if actor is None:
                raise SystemExit(f"{args.email} does not act")
            service, author = ProposalService(session), Principal.agent(args.agent)
            if args.page is not None:
                proposal = await service.propose_change(
                    actor, args.page, args.content, args.reason, author=author
                )
            else:
                proposal = await service.propose_new(
                    actor,
                    args.space,
                    None,
                    args.title or "",
                    args.content,
                    args.reason,
                    author=author,
                )
            await session.commit()
            return {"id": str(proposal.id), "version": proposal.version}
    finally:
        await database.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(seed(arguments()))))
