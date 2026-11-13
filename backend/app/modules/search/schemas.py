import uuid

from pydantic import BaseModel

from app.modules.search.service import HitType, SearchHit


class SearchHitOut(BaseModel):
    """`snippet` is plain text: render it as text and highlight what stands between
    `⟦` and `⟧`. `score` orders the hits (higher is better); it has no unit."""

    type: HitType
    id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    snippet: str
    score: float

    @classmethod
    def of(cls, hit: SearchHit) -> "SearchHitOut":
        return cls(
            type=hit.type,
            id=hit.id,
            space_id=hit.space_id,
            space_name=hit.space_name,
            title=hit.title,
            path=hit.path,
            snippet=hit.snippet,
            score=hit.score,
        )
