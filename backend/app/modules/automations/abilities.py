"""What the caller may do with an automation now (plan M7 decisions 2 and 12 to 14),
from the rules its actions enforce (`service.py`, `control.py`, `takeover.py`), so the
interface offers nothing that would be refused:

- `edit`: its owner (who answers for its words), while she may still own it
  (`standing.may_own`; else the change answers `automation.not_allowed`).
- `pause`: who controls it (its owner, the managers of its place's space,
  `agent.manage`), while it is active.
- `resume`: who controls it, while it is paused and its owner may run it again
  (else the action answers `automation.owner_unable`; take it over instead).
- `delete`: who controls it.
- `run`: its owner, while it is active, and not an event rule.
- `take_over`: someone else who could make it (`standing.may_own`). Its owner
  taking over her own is a harmless no-op and offered to nobody.

The two look-ups that need the database (`owner_may_run`, `may_own`) are asked only
where the rest allows the action, once per agent and place within one answer.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.modules.automations.manage_repository import Row
from app.modules.automations.models import AutomationKind, AutomationState
from app.modules.automations.standing import may_own, owner_may_run

Key = tuple[uuid.UUID, uuid.UUID, AutomationKind]


@dataclass(frozen=True, slots=True)
class Abilities:
    edit: bool
    pause: bool
    resume: bool
    delete: bool
    run: bool
    take_over: bool


@dataclass(slots=True)
class AbilityReader:
    session: AsyncSession
    actor: Actor
    _owning: dict[Key, bool] = field(default_factory=dict)
    _running: dict[tuple[uuid.UUID, Key], bool] = field(default_factory=dict)

    async def of(self, row: Row, *, owner: bool, control: bool) -> Abilities:
        automation = row.automation
        active = automation.state == AutomationState.ACTIVE
        paused = automation.state == AutomationState.PAUSED
        return Abilities(
            edit=owner and await self._may_own(row),
            pause=control and active,
            resume=control and paused and await self._owner_may_run(row),
            delete=control,
            run=owner and active and automation.kind != AutomationKind.EVENT,
            take_over=not owner and await self._may_own(row),
        )

    async def _owner_may_run(self, row: Row) -> bool:
        automation = row.automation
        key = (automation.owner_user_id, _key(row))
        if key not in self._running:
            self._running[key] = await owner_may_run(
                self.session, automation.owner_user_id, row.agent, row.place, automation.kind
            )
        return self._running[key]

    async def _may_own(self, row: Row) -> bool:
        key = _key(row)
        if key not in self._owning:
            self._owning[key] = await may_own(
                self.session, self.actor, row.agent, row.place, row.automation.kind
            )
        return self._owning[key]


def _key(row: Row) -> Key:
    """What `may_own` depends on besides the person: the agent, the place, the kind."""
    return (row.agent.id, row.place.id, row.automation.kind)
