"""New passwords that are easy to guess are refused (ASVS 5.0 V6.2.4, V6.2.11,
V6.2.12): passwords from breaches (the most frequent 142,518 of policy length, any
case) and passwords that contain a word of the context (the product, the
organisation, the person's email or name). Any composition stays allowed."""

import gzip

import pytest
from httpx import AsyncClient

from app.core.password_check import COMMON_FILE
from app.core.password_rule import PASSWORD_MIN_LENGTH
from app.modules.users.models import User
from tests.factories import CSRF, PASSWORD

ADMIN_USERS = "/api/admin/users"


def test_the_breached_list_is_shipped_and_matches_the_policy() -> None:
    with gzip.open(COMMON_FILE, "rt", encoding="utf-8") as f:
        words = f.read().split("\n")[:-1]
    assert len(words) >= 3000  # ASVS: at least the top 3000 of policy length
    assert all(len(w) >= PASSWORD_MIN_LENGTH and w == w.lower() for w in words)
    assert len(set(words)) == len(words)
    assert words[0] == "1234567890"  # most frequent first


async def _change(client: AsyncClient, new: str) -> tuple[int, str]:
    body = {"current_password": PASSWORD, "new_password": new}
    response = await client.post("/api/auth/me/password", json=body, headers=CSRF)
    code = response.json()["error"]["code"] if response.status_code >= 400 else ""
    return response.status_code, code


@pytest.mark.parametrize(
    ("new", "code"),
    [
        ("BasketBall", "auth.password_common"),
        ("correcthorsebatterystaple", "auth.password_common"),
        ("To-Herd-Cats 2026!", "auth.password_context"),
        ("my test org secret", "auth.password_context"),  # the organisation, "Test Org"
        ("owner-for-ever-7", "auth.password_context"),  # owner@example.com
        ("OLGA!loves!tea", "auth.password_context"),  # Olga Owner
    ],
)
async def test_a_guessable_new_password_is_refused(owner: AsyncClient, new: str, code: str) -> None:
    assert await _change(owner, new) == (422, code)


async def test_any_composition_of_an_unguessable_password_is_accepted(owner: AsyncClient) -> None:
    assert await _change(owner, "gelber Kran am Ufer") == (204, "")


async def test_administrators_cannot_set_a_guessable_password(
    owner: AsyncClient, member: User
) -> None:
    new = {"email": "neu@example.com", "name": "Neu Person", "password": "qwertyuiop"}
    created = await owner.post(ADMIN_USERS, json=new)
    assert created.status_code == 422 and created.json()["error"]["code"] == "auth.password_common"
    mine = {**new, "password": "neu-person-2026"}  # the new person's own name
    created = await owner.post(ADMIN_USERS, json=mine)
    assert created.json()["error"]["code"] == "auth.password_context"
    body = {"password": "1234567890", "version": member.version}
    updated = await owner.patch(f"{ADMIN_USERS}/{member.id}", json=body)
    assert updated.status_code == 422 and updated.json()["error"]["code"] == "auth.password_common"
