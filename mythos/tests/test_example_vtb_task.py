from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.core.file_ids import FileIdCodec
from mythos.players.interfaces import PlayerInterfaces
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerCredits, PlayerRecord, PlayerTaskState
from mythos.players.loader import PlayerLoader
from puzzles.example import VTB_TASK_ID, register
from mythos.registry.bundle import RegistryBundle
from mythos.services.tasks import TaskService
from mythos.services.tasks import service as task_service_module


_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


class _TaskClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: int) -> None:
        self.now += timedelta(**delta)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@asynccontextmanager
async def _task_harness(
    tmp_path: Path,
    *,
    vtb: int = 0,
    meta: dict[str, object] | None = None,
    time_1: datetime | None = None,
    time_2: datetime | None = None,
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'task.sqlite3').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    registered = RegistryBundle(Path(__file__).parents[1] / "puzzles")
    register(registered, initial_vtb=0)
    definition = registered.tasks.freeze().task(VTB_TASK_ID)
    registries = RegistryBundle()
    registries.tasks.register(
        definition.task_id,
        definition.handler,
        dependencies=definition.dependencies,
    )
    catalogs = registries.freeze(_FILE_IDS)
    loader = PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS)
    executor = TaskService(catalogs.tasks)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    player_id = uuid4()

    async with session_factory() as session:
        session.add_all(
            [
                PlayerRecord(
                    id=player_id,
                    username="example-task-player",
                    username_normalized="example-task-player",
                ),
                PlayerCredits(player_id=player_id, vtb=vtb, version=0),
                PlayerTaskState(
                    player_id=player_id,
                    task_id=VTB_TASK_ID,
                    time_1=time_1,
                    time_2=time_2,
                    meta=json.dumps(meta or {}, separators=(",", ":")),
                ),
            ]
        )
        await session.commit()
        yield session, executor, loader, player_id

    await engine.dispose()


async def _run_task(session, executor: TaskService, loader: PlayerLoader, player_id: UUID):
    async with session.begin():
        player = await loader.load_writable(
            session,
            player_id,
            interfaces=PlayerInterfaces.TASKS,
        )
        return await executor.run_loaded(session, player)


def test_example_vtb_task_is_lazy_capped_and_persists_meta(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        clock = {"now": datetime(2026, 8, 9, 12, 0, tzinfo=UTC)}
        monkeypatch.setattr(task_service_module, "_utcnow", lambda: clock["now"])
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'example-vtb.sqlite3').as_posix()}",
            checkpoint_directory=tmp_path / "checkpoints",
            task_registry_snapshot_path=tmp_path / "task-registry.json",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        registries = RegistryBundle(settings.puzzle_root)
        register(registries, initial_vtb=0)
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()
        app = create_app(settings, registries=registries, object_store=FakeObjectStore())

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "example-vtb-player", "password": "correct-horse-battery"},
                )
                assert registration.status_code == 201
                access_token = registration.json()["access_token"]
                headers = {"Authorization": f"Bearer {access_token}"}
                async with app.state.database.session_factory() as session:
                    player_id = await session.scalar(
                        select(PlayerRecord.id).where(PlayerRecord.username == "example-vtb-player")
                    )
                    assert isinstance(player_id, UUID)
                    task = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
                    assert task is not None and task.meta == "{}" and task.exception == 0
                    state_before = (task.time_1, task.time_2, task.exception, task.meta)
                    player = await app.state.runtime.player_loader.load(
                        session,
                        player_id,
                        writable=True,
                        interfaces=PlayerInterfaces.TASKS,
                    )
                    assert not await player.tasks.add_task(VTB_TASK_ID)
                    await session.commit()
                    task_after = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
                    assert task_after is not None
                    assert (task_after.time_1, task_after.time_2, task_after.exception, task_after.meta) == state_before

                initial_credit = await client.get("/api/v1/credits", headers=headers)
                initial_tasks = await client.get("/api/v1/tasks", headers=headers)
                assert initial_credit.json()["vtb"] == 0
                assert initial_tasks.json()["tasks"][0]["task_id"] == VTB_TASK_ID
                assert initial_tasks.json()["tasks"][0]["meta"] == {}
                read_only_credit = initial_credit.json()
                read_only_tasks = initial_tasks.json()
                assert (await client.get("/api/v1/credits", headers=headers)).json() == read_only_credit
                assert (await client.get("/api/v1/tasks", headers=headers)).json() == read_only_tasks

                processed = await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert processed.status_code == 200
                assert processed.json()["content"]["tasks"][0]["status"] == "success"
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 5
                initial_state = (await client.get("/api/v1/tasks", headers=headers)).json()["tasks"][0]
                assert initial_state["meta"]["schema_version"] == 1
                assert initial_state["meta"]["initial_grant_applied"] is True
                assert initial_state["meta"]["total_granted"] == 5
                assert initial_state["meta"]["last_granted_at"] == clock["now"].isoformat()
                stored_due = datetime.fromisoformat(initial_state["time_2"])
                if stored_due.tzinfo is None:
                    stored_due = stored_due.replace(tzinfo=UTC)
                assert stored_due == clock["now"] + timedelta(seconds=60)

                async with app.state.database.session_factory() as session:
                    player = await app.state.runtime.player_loader.load(
                        session,
                        player_id,
                        writable=True,
                        interfaces=PlayerInterfaces.CREDITS,
                    )
                    await player.credits.grant_vtb(3)
                    await session.commit()

                clock["now"] += timedelta(seconds=30)
                await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                before_due = (await client.get("/api/v1/credits", headers=headers)).json()
                assert before_due["vtb"] == 8

                clock["now"] += timedelta(seconds=210)
                await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 10
                assert (await client.get("/api/v1/tasks", headers=headers)).json()["tasks"][0]["meta"]["total_granted"] == 7

                clock["now"] += timedelta(seconds=60)
                await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 10

                clock["now"] += timedelta(seconds=60)
                await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 10

                async with app.state.database.session_factory() as session:
                    player = await app.state.runtime.player_loader.load(
                        session,
                        player_id,
                        writable=True,
                        interfaces=PlayerInterfaces.CREDITS,
                    )
                    await player.credits.try_spend_vtb(1)
                    await session.commit()

                clock["now"] += timedelta(seconds=60)
                await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 10

                async with app.state.database.session_factory() as session:
                    task = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
                    credits = await session.get(PlayerCredits, player_id)
                    assert task is not None
                    assert json.loads(task.meta)["total_granted"] == 8
                    assert credits is not None and credits.vtb == 10

    asyncio.run(scenario())


def test_example_vtb_task_defers_before_due_time(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        clock = _TaskClock(datetime(2026, 8, 9, 12, 0, tzinfo=UTC))
        monkeypatch.setattr(task_service_module, "_utcnow", clock)
        async with _task_harness(tmp_path) as (session, executor, loader, player_id):
            await _run_task(session, executor, loader, player_id)
            first = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
            assert first is not None
            first_time_1 = first.time_1
            first_time_2 = first.time_2

            clock.advance(seconds=30)
            await _run_task(session, executor, loader, player_id)
            deferred = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
            credits = await session.get(PlayerCredits, player_id)
            assert deferred is not None
            assert deferred.time_1 == first_time_1
            assert deferred.time_2 == first_time_2
            assert credits is not None and credits.vtb == 5

    asyncio.run(scenario())


def test_example_vtb_task_grants_one_period_and_catches_up_missed_periods(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def scenario() -> None:
        clock = _TaskClock(datetime(2026, 8, 9, 12, 0, tzinfo=UTC))
        monkeypatch.setattr(task_service_module, "_utcnow", clock)
        async with _task_harness(tmp_path) as (session, executor, loader, player_id):
            await _run_task(session, executor, loader, player_id)

            clock.advance(seconds=60)
            await _run_task(session, executor, loader, player_id)
            after_one = await session.get(PlayerCredits, player_id)
            assert after_one is not None and after_one.vtb == 6

            clock.advance(seconds=180)
            await _run_task(session, executor, loader, player_id)
            after_catch_up = await session.get(PlayerCredits, player_id)
            state = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
            assert after_catch_up is not None and after_catch_up.vtb == 9
            assert state is not None
            assert _as_utc(state.time_2) == datetime(2026, 8, 9, 12, 5, tzinfo=UTC)
            assert json.loads(state.meta)["total_granted"] == 9

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("vtb", "expected_grant"),
    ((8, 2), (9, 1), (10, 0)),
)
def test_example_vtb_task_respects_cap_for_initial_execution(
    tmp_path: Path,
    monkeypatch,
    vtb: int,
    expected_grant: int,
) -> None:
    async def scenario() -> None:
        now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
        clock = _TaskClock(now)
        monkeypatch.setattr(task_service_module, "_utcnow", clock)
        async with _task_harness(tmp_path, vtb=vtb) as (session, executor, loader, player_id):
            await _run_task(session, executor, loader, player_id)
            credits = await session.get(PlayerCredits, player_id)
            state = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
            assert credits is not None and credits.vtb == vtb + expected_grant
            assert state is not None
            stored_meta = json.loads(state.meta)
            assert _as_utc(state.time_2) == datetime(2026, 8, 9, 12, 1, tzinfo=UTC)
            if expected_grant:
                assert _as_utc(state.time_1) == now
                assert stored_meta["schema_version"] == 1
                assert stored_meta["initial_grant_applied"] is True
                assert stored_meta["total_granted"] == expected_grant
            else:
                assert state.time_1 is None
                assert stored_meta == {}

    asyncio.run(scenario())


def test_example_vtb_task_reinitializes_old_meta_without_using_meta_for_cap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def scenario() -> None:
        now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
        clock = _TaskClock(now)
        monkeypatch.setattr(task_service_module, "_utcnow", clock)
        async with _task_harness(
            tmp_path,
            vtb=8,
            meta={
                "schema_version": 0,
                "initial_grant_applied": True,
                "total_granted": 100000,
            },
        ) as (session, executor, loader, player_id):
            await _run_task(session, executor, loader, player_id)
            credits = await session.get(PlayerCredits, player_id)
            state = await session.get(PlayerTaskState, (player_id, VTB_TASK_ID))
            assert credits is not None and credits.vtb == 10
            assert state is not None
            assert json.loads(state.meta) == {
                "initial_grant_applied": True,
                "last_granted_at": now.isoformat(),
                "schema_version": 1,
                "total_granted": 100002,
            }

    asyncio.run(scenario())
