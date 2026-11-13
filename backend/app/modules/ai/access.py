"""Who may reach the AI administration. Without `ai.manage` the AI endpoints answer
404 `ai.not_found`, not 403: people without the right learn nothing about the AI
set-up, not even that there is one to be refused (plan M5, global constraints)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import NotFound


def ai_not_found() -> NotFound:
    return NotFound(code="ai.not_found")


async def require_ai(session: AsyncSession, actor: Actor, action: Action) -> None:
    if not await can(session, actor, action):
        raise ai_not_found()
