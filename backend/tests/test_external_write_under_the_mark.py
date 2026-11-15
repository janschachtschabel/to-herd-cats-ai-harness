"""Module review M8 5, L3: under the personal mark, a write tool of a server used
with her own connector asks a personal release (`external_step._before`): what it
writes leaves the system (an issue others read), a write under the mark like any
other, so its card says that what she releases can be read by others now or later."""

from tests.factories_external import Ext, call
from tests.factories_personal import pending
from tests.test_run_external_personal import SECRET, _personal


async def test_an_external_write_under_the_mark_asks_a_personal_release(ext: Ext) -> None:
    search = await _personal(ext)  # her own connector to this server
    await ext.level(4)
    await ext.grant(search_issues="allow", create_issue="allow")
    create = await ext.name("create_issue")
    ext.bench.stub.state.replies.extend(
        [call(search, q="meine"), call(create, title=f"Fund {SECRET}"), {"content": "Ok."}]
    )
    await ext.bench.say("Such meine Issues und leg eins an")
    assert await ext.bench.run_next() is None  # waits for her release
    (approval,) = await pending(ext.bench.people.alice)
    assert approval["tool"] == create and approval["args"] == {"title": f"Fund {SECRET}"}
    assert approval["personal"] is True
