"""Module review M8 3, H5: under the personal mark the person releases only what she
is shown in full. A page change whose diff is beyond `HERD_DIFF_MAX_LINES` cannot be
shown, so it cannot be released: the call is refused with
`personal_release.too_large` (a text the model reads and the run view shows her),
and no card is posted. An approval already asked that has become too large to show
cannot be approved (409 `approval.not_shown_in_full`)."""

import hashlib
import uuid

import pytest

from app.core.config import get_settings
from app.modules.agents.approvals.shown import NOT_SHOWN
from app.modules.agents.run_models import StopReason
from app.modules.spaces.models import AgentWritePolicy
from app.modules.wiki.models import Page
from tests.factories_external import Ext, call
from tests.factories_personal import asks_release, pending
from tests.factories_writing import Work
from tests.test_run_external_personal import SECRET, _personal

CONTENT = f"eins\n{SECRET}\ndrei\n"


def _token(run_id: str, page: Page) -> str:
    """`update_page`'s token for the run (`wiki_tools._token`): bound to the run, the
    page as it is and the new content."""
    parts = (
        run_id,
        str(page.id),
        str(page.version),
        hashlib.sha256(page.content_md.encode()).hexdigest(),
        hashlib.sha256(CONTENT.encode()).hexdigest(),
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


async def _write(ext: Ext, work: Work) -> object:
    """Alice reads through her own connector in her DM; then the agent saves her words
    into a page of the space with the preview's token, in the same run."""
    name = await _personal(ext)
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await work.bench.session.flush()
    page = await work.bench.session.get(Page, uuid.UUID(await work.page("Regeln", "1\n2\n3\n")))
    assert page is not None
    posted = await ext.bench.say("Such meine Issues und schreib sie in die Regeln")
    token = _token(posted["agent_run"]["id"], page)
    save = {"page_id": str(page.id), "content_md": CONTENT, "reason": "neu", "token": token}
    ext.bench.stub.state.replies.extend(
        [call(name, q="meine"), call("update_page", **save), {"content": "Ok."}]
    )
    return await ext.bench.run_next()


async def test_a_change_too_large_to_show_is_refused_unasked(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "diff_max_lines", 4)  # 4 + 4 lines: beyond
    assert await _write(ext, work) == StopReason.COMPLETED
    assert await pending(ext.bench.people.alice) == []
    written = [e for e in await ext.tool_events() if e["name"] == "update_page"][-1]
    assert written["text"] == NOT_SHOWN
    assert "personal_release.too_large" in NOT_SHOWN


async def test_a_change_that_fits_is_asked_with_its_diff(ext: Ext, work: Work) -> None:
    approval = await asks_release(ext, await _write(ext, work))
    r = await ext.bench.people.alice.get(f"/api/approvals/{approval['id']}/diff")
    assert r.status_code == 200 and SECRET in r.text


async def test_an_approval_too_large_to_show_by_now_cannot_be_approved(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = await asks_release(ext, await _write(ext, work))
    monkeypatch.setattr(get_settings(), "diff_max_lines", 4)  # the limit lowered since
    body = {"decision": "approve", "version": approval["version"]}
    r = await ext.bench.people.alice.post(f"/api/approvals/{approval['id']}/decide", json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "approval.not_shown_in_full"
    body = {"decision": "reject", "version": approval["version"]}
    r = await ext.bench.people.alice.post(f"/api/approvals/{approval['id']}/decide", json=body)
    assert r.status_code == 200, r.text  # rejecting needs nothing shown
