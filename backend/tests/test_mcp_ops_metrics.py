"""Plan M8 task 13: what operations sees of M8 besides the tool calls. Codes and
counts only, never a token, a connector's name, a server's address or a file's
content as a label.

- `/mcp` refusals (403 origin, 401 token, 429 rate limit) count in the HTTP metric under
  the route `/mcp` with their status: the alert on token failures reads it.
- OAuth renewals count by the provider's answer (`herd_oauth_refreshes_total{status}`).
- Catalogue files skipped: `herd_mcp_catalog_problems`, set whenever the catalogue is
  read again and on every scrape of an API process.
"""

from pathlib import Path

import httpx
import httpx2
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import REGISTRY
from app.modules.mcp_catalog.loader import catalog
from app.web.internal import create_internal_app
from tests.factories_catalog import entry, write_entry
from tests.factories_dms import People
from tests.factories_mcp_endpoint import INITIALIZE, URL
from tests.factories_tokens import mcp_on, new_token
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub
from tests.test_oauth_tokens import _call, _expire_soon, _shared_server


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _mcp_status(status: int) -> float:
    return _sample("herd_http_requests_total", method="POST", route="/mcp", status=str(status))


async def test_refusals_at_mcp_count_by_status(
    owner: AsyncClient,
    member_client: AsyncClient,
    mcp_http: httpx2.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "mcp_rate_per_minute", 1)
    await mcp_on(owner)
    token = await new_token(member_client)
    before = {s: _mcp_status(s) for s in (200, 401, 403, 429)}
    auth = {"Authorization": f"Bearer {token['secret']}"}
    assert (await mcp_http.post(URL, json=INITIALIZE, headers=auth)).status_code == 200
    assert (await mcp_http.post(URL, json=INITIALIZE, headers=auth)).status_code == 429
    bad = {"Authorization": "Bearer herd_pat_nope"}
    assert (await mcp_http.post(URL, json=INITIALIZE, headers=bad)).status_code == 401
    assert (await mcp_http.post(URL, json=INITIALIZE)).status_code == 401
    browser = {**auth, "Origin": "https://evil.example"}
    assert (await mcp_http.post(URL, json=INITIALIZE, headers=browser)).status_code == 403
    after = {s: _mcp_status(s) - before[s] for s in before}
    assert after == {200: 1, 401: 2, 403: 1, 429: 1}


def _refreshes(status: str) -> float:
    return _sample("herd_oauth_refreshes_total", status=status)


async def test_oauth_renewals_count_by_the_providers_answer(
    oauth_ready: OAuthStub, ai_people: People, mcp_stub: McpStub, session: AsyncSession
) -> None:
    made = await _shared_server(ai_people, oauth_ready, mcp_stub)
    connector_id = made["connector"]["id"]
    before = {s: _refreshes(s) for s in ("ok", "server_error", "invalid_grant")}
    await _expire_soon(session, connector_id)
    await _call(session, ai_people, made["server"]["id"])
    oauth_ready.state.failures.append(503)
    await _expire_soon(session, connector_id)
    with pytest.raises(Exception, match="credential unavailable"):
        await _call(session, ai_people, made["server"]["id"])
    oauth_ready.state.refresh.clear()  # the provider forgot the grant
    await _expire_soon(session, connector_id)
    with pytest.raises(Exception, match="no personal connector"):
        await _call(session, ai_people, made["server"]["id"])
    after = {s: _refreshes(s) - before[s] for s in before}
    assert after == {"ok": 1, "server_error": 1, "invalid_grant": 1}


def _problems() -> float | None:
    return REGISTRY.get_sample_value("herd_mcp_catalog_problems")


def test_skipped_catalogue_files_are_a_gauge(catalog_dir: Path) -> None:
    write_entry(catalog_dir, entry("https://mcp.example/mcp"), "good.yaml")
    (catalog_dir / "broken.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    write_entry(catalog_dir, entry("https://mcp.example/x", id="github"), "dup.yaml")
    catalog()
    assert _problems() == 2
    (catalog_dir / "broken.yaml").unlink()
    (catalog_dir / "dup.yaml").unlink()
    catalog()
    assert _problems() == 0


async def test_a_scrape_of_an_api_process_reads_the_catalogue_again(catalog_dir: Path) -> None:
    catalog()
    assert _problems() == 0
    (catalog_dir / "broken.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    app = create_internal_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://internal") as client:
        r = await client.get("/metrics")
    assert r.status_code == 200
    assert "herd_mcp_catalog_problems 1.0" in r.text
