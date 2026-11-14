"""The OpenAI stub's own behaviour that tests rely on: a scripted reply may wait
(`delay`) after it is taken from the queue, so a request cut off while it waits never
takes a later reply (the e2e worker restart, plan M6 task 13)."""

import asyncio
import time

import httpx

from tests.support.openai_stub import OpenAIStub


async def test_a_reply_with_a_delay_is_taken_first_and_answered_later(
    openai_stub: OpenAIStub,
) -> None:
    openai_stub.state.replies.extend([{"content": "slow", "delay": 0.6}, {"content": "next"}])
    body = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    url = f"{openai_stub.base_url}/chat/completions"
    async with httpx.AsyncClient() as client:
        slow = asyncio.create_task(client.post(url, json=body))
        await asyncio.sleep(0.2)  # the slow request has taken its reply and waits
        started = time.monotonic()
        fast = await client.post(url, json=body)
        assert time.monotonic() - started < 0.5
        assert fast.json()["choices"][0]["message"]["content"] == "next"
        assert not slow.done()  # still waiting with the reply it took
        assert (await slow).json()["choices"][0]["message"]["content"] == "slow"
