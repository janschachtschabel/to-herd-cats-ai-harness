"""A live save racing a Markdown save, over separate connections with real commits
(tests/real_db.py): the page row lock orders them, so the live save either lands
first (and the Markdown save then meets a new version, 409) or meets the new
generation (409); it never writes its older document over the newer Markdown."""

import asyncio
import base64

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import get_settings
from app.web.internal import create_internal_app
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

TOKEN = "r" * 40
ROUNDS = 6


async def test_live_save_never_overwrites_a_markdown_save(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Live", "kind": "team"})).json()
    transport = ASGITransport(app=create_internal_app(), raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://internal", headers={"X-Herd-Internal-Token": TOKEN}
    ) as internal:
        token = owner.cookies.get(get_settings().session_cookie_name)
        outcomes = set()
        for round_ in range(ROUNDS):
            r = await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": f"S{round_}"})
            page = r.json()
            auth = await internal.post(
                "/internal/collab/auth", json={"session_token": token, "page_id": page["id"]}
            )
            assert auth.status_code == 200, auth.text
            sid = auth.json()["session_id"]
            patch, put = await asyncio.gather(
                owner.patch(
                    f"/api/pages/{page['id']}",
                    json={"content_md": "markdown", "version": page["version"]},
                ),
                internal.put(
                    f"/internal/collab/pages/{page['id']}",
                    json={
                        "generation": 0,
                        "ydoc_b64": base64.b64encode(b"old").decode(),
                        "content_md": "live",
                        "editor_session_ids": [sid],
                        "session_key": f"doc-{round_}",
                    },
                ),
            )
            final = (await owner.get(f"/api/pages/{page['id']}")).json()
            if put.status_code == 200:
                assert patch.status_code == 409, patch.text
                assert final["content_md"] == "live"
            else:
                assert put.status_code == 409, put.text
                assert put.json()["error"]["code"] == "collab.generation_ended"
                assert patch.status_code == 200, patch.text
                assert (final["content_md"], final["collab_generation"]) == ("markdown", 1)
            outcomes.add(put.status_code)
    assert outcomes <= {200, 409}
