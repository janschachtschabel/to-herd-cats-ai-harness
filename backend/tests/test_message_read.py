"""One message by id (review M3 N8): for a thread whose parent is not on the loaded
page and for links to a message. The same rule as everywhere: whoever sees the
conversation reads it; anyone else gets 404 `message.not_found`."""

import uuid

from tests.factories_messaging import Chat, post


async def test_a_message_is_read_by_whoever_sees_its_conversation(chat: Chat) -> None:
    top = await post(chat.viewer, chat.channel_id, "oben")
    reply = await post(chat.editor, chat.channel_id, "Antwort", parent_id=top["id"])
    for reader in (chat.viewer2, chat.moderator, chat.admin):
        got = await reader.get(f"/api/messages/{reply['id']}")
        assert got.status_code == 200, got.text
        body = got.json()
        assert (body["id"], body["parent_id"], body["body_md"]) == (
            reply["id"],
            top["id"],
            "Antwort",
        )
        assert body["author"]["id"] == reply["author"]["id"]
    parent = (await chat.viewer2.get(f"/api/messages/{top['id']}")).json()
    assert parent["reply_count"] == 1 and parent["last_reply_at"] is not None


async def test_anyone_else_gets_404(chat: Chat) -> None:
    message = await post(chat.viewer, chat.channel_id, "intern")
    for path in (f"/api/messages/{message['id']}", f"/api/messages/{uuid.uuid4()}"):
        refused = await chat.outsider.get(path)
        assert refused.status_code == 404
        assert refused.json()["error"]["code"] == "message.not_found"
    assert (await chat.viewer.get("/api/messages/kein-id")).status_code == 422
