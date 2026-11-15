"""A tool call's context at `/mcp` (plan M8 decision 3): the person's token as the
writer. What a tool writes through it is the person's (the token's actor holds the
rights, the scope and the policy), with the token's name as the AI mark
(`Authorship.via_token`) and a page version's source `mcp`.

- Keys of what a call writes (a message's `client_id`) are the call's own: every call
  writes anew; nothing is folded into what an earlier call wrote.
- A preview's token (`update_page`) is bound to the access token, so the second call
  that saves may come in another request.
- A token answers in no conversation; it posts in a channel of any space its actor
  may post in (`channel.post`, inside the token's write scope: the service checks).
"""

import uuid
from dataclasses import dataclass

from app.core.authorship import Authorship
from app.modules.agents.toolbox.base import WriteContext
from app.modules.wiki.models import VersionSource


@dataclass(frozen=True, slots=True)
class TokenContext(WriteContext):
    token_id: uuid.UUID
    token_name: str
    call_id: uuid.UUID

    @property
    def by(self) -> Authorship:
        return Authorship(self.actor.principal, via_token=self.token_name)

    @property
    def source(self) -> VersionSource:
        return VersionSource.MCP

    def key(self, name: str, *parts: object) -> uuid.UUID:
        return uuid.uuid5(self.call_id, ":".join([name, *map(str, parts)]))

    def binding(self) -> uuid.UUID:
        return self.token_id

    def answers_in(self, conversation_id: uuid.UUID) -> bool:
        return False

    async def posts_in(self, space_id: uuid.UUID) -> bool:
        return True
