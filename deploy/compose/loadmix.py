"""The load test's scenario (plan M9, decision 20): many people at once, each with an
open live stream and one activity, against one or more API nodes.

    LOAD_PASSWORD=… python loadmix.py STATE SECONDS --bases URL[,URL…] \
        [--think 2.0] [--grace 5] [--settle 10]

STATE comes from loadsetup.py. Every person signs in at node i mod len(bases), opens
`GET /api/stream` there and, after everyone is connected and SETTLE seconds of quiet,
repeats one activity for SECONDS, with a pause of THINK × 0.5 … 1.5 seconds between
two actions. The mix (in steps of 5 %, by person):

    page_read 40 %   GET /api/pages/{id} (a page of the team)
    search 10 %      GET /api/search?q=<two words>
    message_write 15 %  POST /api/conversations/{team channel}/messages
    ticket_move 10 % PATCH /api/tickets/{n} (own ticket to the next status)
    board 15 %       GET /api/spaces/{id}/board and GET /api/tickets?assignee=me, in turn
    page_save 10 %   PATCH /api/pages/{id} (an own page of the team)

Live delivery: the time from sending a message to `message.created` with its id on
every stream of the team (the author's included); events still missing GRACE seconds
after the end count as lost. loadreport.py judges against the targets.
"""

import argparse
import asyncio
import json
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx
from loadreport import Sample, render

HEADERS = {"X-Requested-With": "herd"}
PATTERN = (
    ["page_read"] * 8
    + ["search"] * 2
    + ["message_write"] * 3
    + ["ticket_move"] * 2
    + ["board"] * 3
    + ["page_save"] * 2
)  # 20 slots of 5 %
WORDS = "angebot bericht budget handbuch kunde planung projekt server termin urlaub".split()


@dataclass
class Person:
    index: int
    email: str
    activity: str
    team: dict[str, Any]
    tickets: list[int]
    client: httpx.AsyncClient
    own_page: str | None = None
    versions: dict[str, int] = field(default_factory=dict)  # page id or ticket number


@dataclass
class Run:
    samples: list[Sample] = field(default_factory=list)
    sent: dict[str, tuple[float, int]] = field(default_factory=dict)  # message → (t, team)
    arrived: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    connected: int = 0
    stream_errors: int = 0
    expected: int = 0
    all_open: asyncio.Event = field(default_factory=asyncio.Event)

    def opened(self, ok: bool) -> None:
        if ok:
            self.connected += 1
        else:
            self.stream_errors += 1
        if self.connected + self.stream_errors >= self.expected:
            self.all_open.set()


async def _timed(run: Run, name: str, request: Any) -> httpx.Response | None:
    started = time.monotonic()
    try:
        response: httpx.Response = await request
    except httpx.HTTPError as exc:
        run.samples.append(Sample(name, time.monotonic() - started, type(exc).__name__))
        return None
    run.samples.append(Sample(name, time.monotonic() - started, str(response.status_code)))
    return response


async def _stream(person: Person, run: Run, stop: asyncio.Event) -> None:
    answered = False
    try:
        async with person.client.stream("GET", "/api/stream", timeout=None) as response:
            answered = True
            run.opened(response.status_code == 200)
            if response.status_code != 200:
                return
            event = ""
            async for line in response.aiter_lines():
                if stop.is_set():
                    return
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event == "message.created":
                    run.arrived[json.loads(line[6:])["message_id"]].append(time.monotonic())
    except httpx.HTTPError:
        if not answered:
            run.opened(False)
        elif not stop.is_set():
            run.stream_errors += 1


async def _act(person: Person, run: Run, rng: random.Random, turn: int) -> None:
    team, c = person.team, person.client
    body: dict[str, Any]
    if person.activity == "page_read":
        await _timed(run, "page_read", c.get(f"/api/pages/{rng.choice(team['page_ids'])}"))
    elif person.activity == "search":
        q = " ".join(rng.sample(WORDS, 2))
        await _timed(run, "search", c.get("/api/search", params={"q": q, "limit": 20}))
    elif person.activity == "message_write":
        body = {"body_md": " ".join(rng.choices(WORDS, k=12)), "parent_id": None, "mentions": []}
        sent = time.monotonic()
        path = f"/api/conversations/{team['channel_id']}/messages"
        response = await _timed(run, "message_write", c.post(path, json=body, headers=HEADERS))
        if response is not None and response.status_code == 201:
            run.sent[response.json()["id"]] = (sent, team["index"])
    elif person.activity == "ticket_move":
        number = person.tickets[turn % len(person.tickets)]
        statuses = team["status_ids"]
        body = {
            "status_id": statuses[turn % len(statuses)],
            "version": person.versions[str(number)],
        }
        response = await _timed(
            run, "ticket_move", c.patch(f"/api/tickets/{number}", json=body, headers=HEADERS)
        )
        if response is not None and response.status_code == 200:
            person.versions[str(number)] = response.json()["version"]
    elif person.activity == "board":
        if turn % 2 == 0:
            await _timed(run, "board", c.get(f"/api/spaces/{team['space_id']}/board"))
        else:
            mine = c.get("/api/tickets", params={"assignee": "me", "limit": 50})
            await _timed(run, "my_tickets", mine)
    elif person.activity == "page_save":
        assert person.own_page is not None
        body = {
            "content_md": f"# Seite\n\nStand {turn}: " + " ".join(rng.choices(WORDS, k=300)),
            "version": person.versions[person.own_page],
        }
        path = f"/api/pages/{person.own_page}"
        response = await _timed(run, "page_save", c.patch(path, json=body, headers=HEADERS))
        if response is not None and response.status_code == 200:
            person.versions[person.own_page] = response.json()["version"]


async def _loop(person: Person, run: Run, until: float, think: float) -> None:
    rng = random.Random(person.index)  # noqa: S311 - load data, not secrets
    await asyncio.sleep(rng.uniform(0, think))  # not everyone at the same instant
    turn = 0
    while time.monotonic() < until:
        await _act(person, run, rng, turn)
        turn += 1
        await asyncio.sleep(think * rng.uniform(0.5, 1.5))


async def _prepare(person: Person, password: str) -> None:
    body = {"email": person.email, "password": password}
    response = await person.client.post("/api/auth/login", json=body, headers=HEADERS)
    response.raise_for_status()
    if person.activity == "ticket_move":
        for number in person.tickets:
            ticket = (await person.client.get(f"/api/tickets/{number}")).json()
            person.versions[str(number)] = ticket["version"]
    if person.activity == "page_save":
        assert person.own_page is not None
        page = (await person.client.get(f"/api/pages/{person.own_page}")).json()
        person.versions[person.own_page] = page["version"]


def _people(state: dict[str, Any], bases: list[str]) -> list[Person]:
    people: list[Person] = []
    savers: dict[int, int] = defaultdict(int)
    for t, team in enumerate(state["teams"]):
        team["index"] = t
        for member in team["people"]:
            i = len(people)
            activity = PATTERN[i % len(PATTERN)]
            client = httpx.AsyncClient(base_url=bases[i % len(bases)], timeout=30)
            person = Person(i, member["email"], activity, team, member["tickets"], client)
            if activity == "page_save":
                person.own_page = team["page_ids"][savers[t]]
                savers[t] += 1
            people.append(person)
    return people


def _live(run: Run, state: dict[str, Any]) -> tuple[list[float], int]:
    size = {t: len(team["people"]) for t, team in enumerate(state["teams"])}
    delays, missing = [], 0
    for message, (sent, team) in run.sent.items():
        arrivals = run.arrived.get(message, [])
        delays += [at - sent for at in arrivals]
        missing += max(0, size[team] - len(arrivals))
    return delays, missing


async def main(args: argparse.Namespace, state: dict[str, Any]) -> None:
    people = _people(state, args.bases.split(","))
    run, stop = Run(), asyncio.Event()
    gate = asyncio.Semaphore(8)

    async def prepare(person: Person) -> None:
        async with gate:
            await _prepare(person, os.environ["LOAD_PASSWORD"])

    await asyncio.gather(*(prepare(p) for p in people))
    streams = [asyncio.create_task(_stream(p, run, stop)) for p in people]
    run.expected = len(people)
    await run.all_open.wait()
    print(f"{run.connected} streams open ({run.stream_errors} failed); settle {args.settle}s")
    await asyncio.sleep(args.settle)
    print(
        f"start {time.strftime('%H:%M:%S')}: {len(people)} people for {args.seconds}s", flush=True
    )
    started = time.monotonic()
    until = started + args.seconds
    await asyncio.gather(*(_loop(p, run, until, args.think) for p in people))
    elapsed = time.monotonic() - started
    print(f"end {time.strftime('%H:%M:%S')}", flush=True)
    await asyncio.sleep(args.grace)
    stop.set()
    for task in streams:
        task.cancel()
    await asyncio.gather(*streams, return_exceptions=True)
    for person in people:
        await person.client.aclose()
    delays, missing = _live(run, state)
    print(f"messages {len(run.sent)}, deliveries {len(delays)}, stream errors {run.stream_errors}")
    print(render(run.samples, live_delays=delays, live_missing=missing, seconds=elapsed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("state")
    parser.add_argument("seconds", type=float)
    parser.add_argument("--bases", required=True)
    parser.add_argument("--think", type=float, default=2.0)
    parser.add_argument("--grace", type=float, default=5.0)
    parser.add_argument("--settle", type=float, default=10.0)
    arguments = parser.parse_args()
    with open(arguments.state, encoding="utf-8") as source:
        asyncio.run(main(arguments, json.load(source)))
