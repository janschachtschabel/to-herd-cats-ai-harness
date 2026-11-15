"""A tool call's context at `/mcp` (plan M8 decision 3): the token as the writer. What
a tool writes through a personal token is the person's (the token's actor holds the
rights, the scope and the policy); through an agent token (decision 11) the external
agent's (`agent_id`), with the responsible person's rights held to the agent's roles.
Either way with the token's name as the AI mark (`Authorship.via_token`) and a page
version's source `mcp`; an agent's message is of kind `agent`, mentions nobody and
starts no run.

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
from app.core.principal import Principal
from app.modules.agents.toolbox.base import WriteContext
from app.modules.wiki.models import VersionSource


@dataclass(frozen=True, slots=True)
class TokenContext(WriteContext):
    token_id: uuid.UUID
    token_name: str
    call_id: uuid.UUID
    agent_id: uuid.UUID | None = None  # an agent token's external agent

    @property
    def agent_self(self) -> uuid.UUID | None:
        return self.agent_id

    @property
    def by(self) -> Authorship:
        author = Principal.agent(self.agent_id) if self.agent_id else self.actor.principal
        return Authorship(author, via_token=self.token_name)

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
