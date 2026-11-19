"""A personal card worded as a read ("Dabei wird nichts geschrieben") is only for
tools that write nothing: `ask_user` posts its question once released and
`submit_result` makes its text the run's answer, so neither is `reads` (module
review M8 6, M1)."""

from sqlalchemy import select

from app.modules.messaging.models import Message, MessageKind
from tests.factories_external import Ext, call
from tests.factories_personal import decide, pending
from tests.test_personal_release_confirm import _confirm
from tests.test_run_external_personal import SECRET, _personal


async def test_ask_user_under_the_mark_is_not_worded_as_a_read(ext: Ext) -> None:
    name = await _personal(ext)
    await _confirm(ext, "ask_user", name)
    question = f"Soll ich {SECRET} melden?"
    ext.bench.stub.state.replies.extend(
        [call(name, q="meine"), call("ask_user", question=question), {"content": "Ok."}]
    )
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() is None  # waits for her release
    (approval,) = await pending(ext.bench.people.alice)
    assert approval["tool"] == "ask_user" and approval["personal"] is True
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() is None  # now waits for her answer
    written = list(
        await ext.bench.session.scalars(
            select(Message.body_md).where(Message.kind == MessageKind.QUESTION)
        )
    )
    assert written == [question]  # released as "nothing is written", and written
    assert approval["reads"] is False, "the card told her nothing would be written"


async def test_submit_result_under_the_mark_is_not_worded_as_a_read(ext: Ext) -> None:
    name = await _personal(ext)
    await _confirm(ext, "submit_result", name)
    text = f"Ergebnis: {SECRET}"
    ext.bench.stub.state.replies.extend([call(name, q="meine"), call("submit_result", text=text)])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() is None  # waits for her release
    (approval,) = await pending(ext.bench.people.alice)
    assert approval["tool"] == "submit_result" and approval["personal"] is True
    await decide(ext, approval, "approve")
    await ext.bench.run_next()
    answers = [m for m in await ext.bench.messages() if m["body_md"] == text]
    assert len(answers) == 1  # released as "nothing is written", and written
    assert approval["reads"] is False, "the card told her nothing would be written"
