"""What event rules listen to (plan M7 task 5, decisions 8 and 9): an event a run's
step caused names the run (`event_outbox.run_id`, set by the step host for whatever
the step's tool emits, never by the services themselves); an upload emits
`attachment.uploaded` with ids only."""

import uuid

from app.core.outbox import Event
from app.modules.agents.models import StopReason
from tests.factories_tools import call
from tests.factories_writing import Work, events
from tests.test_wiki_attachments import PNG, _uploaded


async def test_an_event_a_runs_tool_caused_names_the_run(work: Work) -> None:
    bench = work.bench
    bench.agent.level = 2
    await bench.session.flush()
    await work.ticket("Von Hand")  # a person's: no run
    args = {"space_id": str(work.space.id), "title": "Vom Agenten"}
    bench.stub.state.replies.extend([call("create_ticket", **args), {"content": "Angelegt."}])
    await bench.say("Lege ein Ticket an")
    assert await bench.run_next() == StopReason.COMPLETED
    by_hand, by_run = await events(bench.session, "ticket.created")
    assert by_hand.run_id is None
    run = by_run.run_id
    assert run is not None and (await bench.run_of(run)).agent_id == bench.agent.id
    assert Event.of(by_run).run_id == run
    answered = (await events(bench.session, "message.created"))[-1]
    assert answered.run_id is None  # the answer is the run's end, not a step's tool


async def test_an_upload_emits_attachment_uploaded_with_ids_only(work: Work) -> None:
    page_id = await work.page()
    made = await _uploaded(work.admin, {"id": page_id}, "plan.png", PNG)
    (event,) = await events(work.bench.session, "attachment.uploaded")
    assert (event.subject_type, event.subject_id, event.space_id) == (
        "attachment",
        uuid.UUID(made["id"]),
        work.space.id,
    )
    assert event.payload == {"attachment_id": made["id"], "page_id": page_id}
    assert event.run_id is None
