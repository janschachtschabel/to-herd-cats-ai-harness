"""Skill schemas. Lengths are checked by the service with their own error codes
(`skill.name_invalid`, `skill.description_invalid`, `skill.content_invalid`)."""

import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict

from app.core.principal import Principal, PrincipalType
from app.modules.skills.models import Skill, SkillState, SkillVersion


class SkillCreate(BaseModel):
    """`space_id`: the space the skill belongs to; none: organisation-wide."""

    model_config = ConfigDict(extra="forbid")

    space_id: uuid.UUID | None = None
    name: str
    description: str
    content: str


class SkillUpdate(BaseModel):
    """Only what is given changes; a given field cannot be null."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: str | None = None
    description: str | None = None
    content: str | None = None


class SkillVersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


class SkillAuthorOut(BaseModel):
    """`name`: the person's or agent's name (none if it is gone)."""

    type: PrincipalType
    id: uuid.UUID
    name: str | None

    @classmethod
    def of(cls, type_: str, id_: uuid.UUID, names: dict[Principal, str]) -> Self:
        principal = Principal(PrincipalType(type_), id_)
        return cls(type=principal.type, id=id_, name=names.get(principal))


class SkillOut(BaseModel):
    """A skill without its text (lists)."""

    id: uuid.UUID
    space_id: uuid.UUID | None
    name: str
    description: str
    state: SkillState
    author: SkillAuthorOut
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def fields(cls, skill: Skill, names: dict[Principal, str]) -> dict[str, Any]:
        return {
            "id": skill.id,
            "space_id": skill.space_id,
            "name": skill.name,
            "description": skill.description,
            "state": skill.state,
            "author": SkillAuthorOut.of(skill.author_type, skill.author_id, names),
            "version": skill.version,
            "created_at": skill.created_at,
            "updated_at": skill.updated_at,
        }

    @classmethod
    def of(cls, skill: Skill, names: dict[Principal, str]) -> Self:
        return cls(**cls.fields(skill, names))


class SkillDetailOut(SkillOut):
    """A skill with its instructions (`content`, Markdown)."""

    content: str

    @classmethod
    def of(cls, skill: Skill, names: dict[Principal, str]) -> Self:
        return cls(**cls.fields(skill, names), content=skill.content)


class SkillVersionOut(BaseModel):
    number: int
    description: str
    author: SkillAuthorOut
    created_at: datetime

    @classmethod
    def fields(cls, version: SkillVersion, names: dict[Principal, str]) -> dict[str, Any]:
        return {
            "number": version.number,
            "description": version.description,
            "author": SkillAuthorOut.of(version.author_type, version.author_id, names),
            "created_at": version.created_at,
        }

    @classmethod
    def of(cls, version: SkillVersion, names: dict[Principal, str]) -> Self:
        return cls(**cls.fields(version, names))


class SkillVersionDetailOut(SkillVersionOut):
    content: str

    @classmethod
    def of(cls, version: SkillVersion, names: dict[Principal, str]) -> Self:
        return cls(**cls.fields(version, names), content=version.content)
