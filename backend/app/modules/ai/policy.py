"""The AI policy of a space (spec 7.3) as pure rules, for the agent loop (before every
model call) and the indexing (which spaces get embeddings).

- `any` (default): every connection may receive the space's content.
- `restricted`: only connections whose `data_location` is in `allowed_locations`.
- `none`: AI does not see the space at all (no tool returns it, no embeddings).

A run reads content from several spaces; it is held to the strictest of their
policies (`strictest`), and a connection may receive its content only if it meets
that one (`connection_allowed`).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.modules.ai.models import AiConnection, AiPolicy, DataLocation

ALL_LOCATIONS = frozenset(DataLocation)


@dataclass(frozen=True, slots=True)
class Policy:
    kind: AiPolicy
    allowed: frozenset[DataLocation]

    @classmethod
    def of(cls, kind: str, allowed_locations: Sequence[str] = ()) -> "Policy":
        policy = AiPolicy(kind)
        if policy == AiPolicy.ANY:
            return ANY
        if policy == AiPolicy.NONE:
            return NONE
        return cls(policy, frozenset(DataLocation(loc) for loc in allowed_locations))

    def locations(self) -> frozenset[DataLocation]:
        """The data locations that may receive content under this policy."""
        if self.kind == AiPolicy.ANY:
            return ALL_LOCATIONS
        if self.kind == AiPolicy.NONE:
            return frozenset()
        return self.allowed


ANY = Policy(AiPolicy.ANY, ALL_LOCATIONS)
NONE = Policy(AiPolicy.NONE, frozenset())


def strictest(policies: Iterable[Policy]) -> Policy:
    """The policy all of them together demand: `none` if any is `none`; otherwise the
    locations every one of them allows (`restricted`, possibly to none at all), or
    `any` if all are `any`."""
    result = ANY
    for policy in policies:
        if policy.kind == AiPolicy.NONE:
            return NONE
        if policy.kind == AiPolicy.RESTRICTED:
            result = Policy(AiPolicy.RESTRICTED, result.locations() & policy.allowed)
    return result


def connection_allowed(connection: AiConnection | DataLocation | str, policy: Policy) -> bool:
    """Whether a connection (or one at that data location) may receive content held to
    `policy`."""
    if isinstance(connection, AiConnection):
        connection = connection.data_location
    return DataLocation(connection) in policy.locations()
