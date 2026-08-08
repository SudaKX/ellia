from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import CommandTransactionExecutor, RequestCache, ResponseSpec
from mythos.core.config import Settings
from mythos.core.file_ids import FileIdCodec
from mythos.core.player_interfaces import PlayerInterfaces
from mythos.persistence.base import Base
from mythos.persistence.models import (
    PlayerCredits,
    PlayerAuth,
    PlayerProgress,
    PlayerProgressCheckpoint,
    PlayerProgressFrontierNode,
    PlayerProgressUnlockedNode,
    PlayerRecord,
    PlayerTaskState,
)
from mythos.players.factory import PlayerFactory
from mythos.players.interfaces import ReadOnlyTaskError, TaskMetaError
from mythos.registry.accounts import VirtualAccountTemplate
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.registry.tasks import TaskHandlerError
from mythos.registry.tasks import TaskRegistry, TaskSnapshot
from mythos.registry.errors import RegistryError
from mythos.main import create_app
from mythos.services.tasks import (
    TaskCatalogEmptyError,
    TaskExecutor,
    TaskReconciliationRunner,
    TaskSnapshotError,
    TaskSnapshotStore,
)
from mythos.services.progress import LocalCheckpointStore, ProgressCheckpointHook

pytestmark = pytest.mark.anyio

_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as current:
        yield current
    await engine.dispose()


def _registries(*handlers):
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("start", (), is_entry=True))
    registries.accounts.register_template(VirtualAccountTemplate("test.account", "Test", permission=1))
    for task_id, handler in handlers:
        registries.tasks.register(task_id, handler, dependencies=PlayerInterfaces.CREDITS)
    return registries


async def _seed_player(session, *, task_ids: tuple[str, ...]) -> tuple[object, object]:
    player_id = uuid4()
    progress = PlayerProgress(player_id=player_id, version=1)
    session.add_all(
        [
            PlayerRecord(id=player_id, username="task-player", username_normalized="task-player"),
            progress,
            PlayerCredits(player_id=player_id, vtb=0, version=0),
            *[PlayerTaskState(player_id=player_id, task_id=task_id, meta="{}") for task_id in task_ids],
        ]
    )
    await session.commit()
    return player_id, progress


def _executor(registries: RegistryBundle) -> TaskExecutor:
    catalogs = registries.freeze(_FILE_IDS)
    factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
    return TaskExecutor(factory, catalogs.tasks)


def test_task_registry_freezes_handler_identity_and_snapshot() -> None:
    registry = TaskRegistry()

    @registry.task("test.decorated", dependencies=PlayerInterfaces.CREDITS)
    async def handler(_context) -> None:
        return None

    catalog = registry.freeze()
    assert catalog.task("test.decorated").handler is handler
    assert catalog.task("test.decorated").dependencies == PlayerInterfaces.CREDITS
    assert TaskSnapshot.from_dict(catalog.snapshot().as_dict()) == catalog.snapshot()

    with pytest.raises(RegistryError):
        registry.task("test.invalid")(lambda _context: None)


async def test_read_only_task_interface_rejects_mutation(session) -> None:
    async def handler(_context) -> None:
        return None

    registries = _registries(("test.task", handler))
    player_id, _ = await _seed_player(session, task_ids=())
    catalogs = registries.freeze(_FILE_IDS)
    player = await PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS).load(
        session,
        player_id,
        writable=False,
        interfaces=PlayerInterfaces.TASKS,
    )

    with pytest.raises(ReadOnlyTaskError):
        await player.tasks.add_task("test.task")


async def test_task_add_then_remove_is_idempotent_in_one_transaction(session) -> None:
    async def handler(_context) -> None:
        return None

    registries = _registries(("test.task", handler))
    player_id, _ = await _seed_player(session, task_ids=())
    catalogs = registries.freeze(_FILE_IDS)
    player = await PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS).load(
        session,
        player_id,
        writable=True,
        interfaces=PlayerInterfaces.TASKS,
    )
    await session.commit()

    async with session.begin():
        assert await player.tasks.add_task("test.task")
        assert await player.tasks.remove_task("test.task")
        assert not await player.tasks.remove_task("test.task")
        assert await player.tasks.add_task("test.task")

    assert await session.get(PlayerTaskState, (player_id, "test.task")) is not None


async def test_task_executor_updates_context_state_and_time(session) -> None:
    async def handler(context) -> None:
        await context.player.credits.grant_vtb(3)
        context.set_extra_time(context.now)
        context.update_meta({"runs": 1})

    registries = _registries(("test.task", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.task",))
    executor = _executor(registries)

    async with session.begin():
        report = await executor.run_itx(session, player_id)

    state = await session.get(PlayerTaskState, (player_id, "test.task"))
    credits = await session.get(PlayerCredits, player_id)
    assert report.body() == {
        "tasks": [{"task_id": "test.task", "status": "success", "exception": 0}]
    }
    assert state is not None and state.time_1 is not None and state.time_2 is not None
    assert state.meta == '{"runs":1}'
    assert credits is not None and credits.vtb == 3


async def test_handler_error_rolls_back_and_reloads_player_for_next_task(session) -> None:
    async def failing(context) -> None:
        await context.player.credits.grant_vtb(10)
        raise TaskHandlerError("expected failure")

    async def succeeding(context) -> None:
        await context.player.credits.grant_vtb(2)

    registries = _registries(("test.failed", failing), ("test.success", succeeding))
    player_id, _ = await _seed_player(session, task_ids=("test.failed", "test.success"))
    executor = _executor(registries)

    async with session.begin():
        report = await executor.run_itx(session, player_id)

    states = {
        state.task_id: state
        for state in (await session.scalars(select(PlayerTaskState).where(PlayerTaskState.player_id == player_id))).all()
    }
    credits = await session.get(PlayerCredits, player_id)
    assert [run.status.value for run in report.runs] == ["failure", "success"]
    assert states["test.failed"].exception == 1
    assert states["test.failed"].time_1 is None
    assert states["test.success"].time_1 is not None
    assert credits is not None and credits.vtb == 2


async def test_defer_preserves_time_1(session) -> None:
    old_time = datetime(2026, 1, 1, tzinfo=UTC)

    async def handler(context) -> None:
        context.defer()
        context.set_extra_time(context.now)

    registries = _registries(("test.defer", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.defer",))
    state = await session.get(PlayerTaskState, (player_id, "test.defer"))
    assert state is not None
    state.time_1 = old_time
    await session.commit()

    async with session.begin():
        await _executor(registries).run_itx(session, player_id)

    state = await session.get(PlayerTaskState, (player_id, "test.defer"))
    assert state is not None and state.time_1 == old_time and state.time_2 is not None


async def test_task_added_during_execution_waits_for_next_round(session) -> None:
    calls = 0

    async def first(context) -> None:
        await context.player.tasks.add_task("test.second")

    async def second(_context) -> None:
        nonlocal calls
        calls += 1

    registries = _registries(("test.first", first), ("test.second", second))
    player_id, _ = await _seed_player(session, task_ids=("test.first",))
    executor = _executor(registries)

    async with session.begin():
        await executor.run_itx(session, player_id)
    assert calls == 0
    assert await session.get(PlayerTaskState, (player_id, "test.second")) is not None

    async with session.begin():
        await executor.run_itx(session, player_id)
    assert calls == 1


async def test_invalid_task_meta_aborts_the_task_transaction(session) -> None:
    async def handler(context) -> None:
        context.replace_meta({"value": float("nan")})

    registries = _registries(("test.meta", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.meta",))
    executor = _executor(registries)

    with pytest.raises(TaskMetaError):
        async with session.begin():
            await executor.run_itx(session, player_id)

    state = await session.get(PlayerTaskState, (player_id, "test.meta"))
    assert state is not None and state.time_1 is None and state.meta == "{}"


async def test_task_and_operation_transactions_are_independent(session) -> None:
    calls = 0

    async def handler(context) -> None:
        nonlocal calls
        calls += 1
        await context.player.credits.grant_vtb(1)

    registries = _registries(("test.task", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.task",))
    catalogs = registries.freeze(_FILE_IDS)
    factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
    task_executor = TaskExecutor(factory, catalogs.tasks)
    executor = CommandTransactionExecutor(
        factory,
        RequestCache(maxsize=4, ttl_seconds=60),
        task_executor=task_executor,
    )
    identity = PlayerIdentity(player_id=player_id)

    async def operation(_context) -> ResponseSpec:
        raise RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"):
        await executor.execute_with_task(session, identity, uuid4(), operation)

    credits = await session.get(PlayerCredits, player_id)
    state = await session.get(PlayerTaskState, (player_id, "test.task"))
    assert calls == 1
    assert credits is not None and credits.vtb == 1
    assert state is not None and state.time_1 is not None


async def test_execute_with_task_replay_does_not_rerun_tasks(session) -> None:
    calls = 0

    async def handler(context) -> None:
        nonlocal calls
        calls += 1

    registries = _registries(("test.task", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.task",))
    catalogs = registries.freeze(_FILE_IDS)
    factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
    executor = CommandTransactionExecutor(
        factory,
        RequestCache(maxsize=4, ttl_seconds=60),
        task_executor=TaskExecutor(factory, catalogs.tasks),
    )
    identity = PlayerIdentity(player_id=player_id)
    request_id = uuid4()

    async def operation(_context) -> ResponseSpec:
        return ResponseSpec(status_code=200, body={"ok": True}, headers={})

    first = await executor.execute_with_task(session, identity, request_id, operation)
    replay = await executor.execute_with_task(session, identity, request_id, operation)
    assert first is replay
    assert calls == 1


def test_task_http_endpoints_process_and_replay(tmp_path) -> None:
    async def scenario() -> None:
        calls = 0
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", (), is_entry=True))

        @registries.tasks.task("test.http-task", dependencies=PlayerInterfaces.CREDITS)
        async def handler(_context) -> None:
            nonlocal calls
            calls += 1
            await _context.player.credits.grant_vtb(4)

        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'tasks-http.sqlite3').as_posix()}",
            task_registry_snapshot_path=tmp_path / "task-registry.json",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries, object_store=FakeObjectStore())

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "task-http-player", "password": "correct-horse-battery"},
                )
                assert registered.status_code == 201
                token = registered.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                async with app.state.database.session_factory() as session:
                    player_id = await session.scalar(
                        select(PlayerRecord.id).where(PlayerRecord.username == "task-http-player")
                    )
                    assert isinstance(player_id, UUID)
                    await session.commit()
                    async with session.begin():
                        player = await app.state.runtime.player_factory.load(
                            session,
                            player_id,
                            writable=True,
                            interfaces=PlayerInterfaces.TASKS,
                        )
                        assert await player.tasks.add_task("test.http-task")

                listing = await client.get("/api/v1/tasks", headers=headers)
                assert listing.status_code == 200
                assert listing.json()["tasks"][0]["task_id"] == "test.http-task"

                request_id = str(uuid4())
                processed = await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": request_id},
                )
                assert processed.status_code == 200
                assert processed.json()["content"]["tasks"] == [
                    {"task_id": "test.http-task", "status": "success", "exception": 0}
                ]
                replay = await client.post(
                    "/api/v1/tasks/process",
                    headers={**headers, "Request-ID": request_id},
                )
                assert replay.json() == processed.json()

            async with app.state.database.session_factory() as session:
                credits = await session.get(PlayerCredits, player_id)
                assert credits is not None and credits.vtb == 4
                assert calls == 1

    import asyncio

    asyncio.run(scenario())


def test_login_task_failure_rolls_back_auth_mutations(tmp_path) -> None:
    async def scenario() -> None:
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", (), is_entry=True))

        @registries.tasks.task("test.auth-failure")
        async def handler(_context) -> None:
            raise RuntimeError("task infrastructure failed")

        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'auth-task-failure.sqlite3').as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries, object_store=FakeObjectStore())

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "auth-task-player", "password": "correct-horse-battery"},
                )
                assert registered.status_code == 201

                async with app.state.database.session_factory() as session:
                    player_id = await session.scalar(
                        select(PlayerRecord.id).where(PlayerRecord.username == "auth-task-player")
                    )
                    assert isinstance(player_id, UUID)
                    auth_before = await session.get(PlayerAuth, player_id)
                    assert auth_before is not None
                    await session.commit()
                    session.add(PlayerTaskState(player_id=player_id, task_id="test.auth-failure", meta="{}"))
                    await session.commit()

                failed_login = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "auth-task-player", "password": "correct-horse-battery"},
                )
                assert failed_login.status_code == 500

                async with app.state.database.session_factory() as session:
                    auth_after = await session.get(PlayerAuth, player_id)
                    assert auth_after is not None
                    assert auth_after.refresh_selector == auth_before.refresh_selector
                    assert auth_after.refresh_secret_hash == auth_before.refresh_secret_hash
                    assert auth_after.refresh_rotated_at == auth_before.refresh_rotated_at

    import asyncio

    asyncio.run(scenario())


def test_logout_processes_authenticated_player_tasks(tmp_path) -> None:
    async def scenario() -> None:
        calls = 0
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", (), is_entry=True))

        @registries.tasks.task("test.logout-task")
        async def handler(_context) -> None:
            nonlocal calls
            calls += 1

        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'logout-task.sqlite3').as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries, object_store=FakeObjectStore())

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "logout-task-player", "password": "correct-horse-battery"},
                )
                token = registered.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                async with app.state.database.session_factory() as session:
                    player_id = await session.scalar(
                        select(PlayerRecord.id).where(PlayerRecord.username == "logout-task-player")
                    )
                    assert isinstance(player_id, UUID)
                    session.add(PlayerTaskState(player_id=player_id, task_id="test.logout-task", meta="{}"))
                    await session.commit()

                logged_out = await client.post("/api/v1/auth/logout", headers=headers)
                assert logged_out.status_code == 204
                assert calls == 1

                async with app.state.database.session_factory() as session:
                    task = await session.get(PlayerTaskState, (player_id, "test.logout-task"))
                    assert task is not None and task.time_1 is not None

    import asyncio

    asyncio.run(scenario())


def test_task_reconciliation_removes_stale_rows_and_writes_snapshot(tmp_path) -> None:
    async def scenario() -> None:
        async def valid_handler(_context) -> None:
            return None

        registries = _registries(("test.valid", valid_handler))
        catalogs = registries.freeze(_FILE_IDS)
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'reconcile.sqlite3').as_posix()}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        player_id = uuid4()
        async with session_factory() as session:
            session.add_all(
                [
                    PlayerRecord(id=player_id, username="reconcile-player", username_normalized="reconcile-player"),
                    PlayerProgress(player_id=player_id, version=1),
                    PlayerTaskState(player_id=player_id, task_id="test.valid", meta="{}"),
                    PlayerTaskState(player_id=player_id, task_id="test.stale", meta="{}"),
                ]
            )
            await session.commit()
        factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
        command_executor = CommandTransactionExecutor(factory, RequestCache(maxsize=4, ttl_seconds=60))
        snapshot_store = TaskSnapshotStore(tmp_path / "task-registry.json")
        runner = TaskReconciliationRunner(
            session_factory,
            command_executor,
            catalogs.tasks,
            snapshot_store,
        )

        await runner.run()

        async with session_factory() as session:
            task_ids = tuple(
                (
                    await session.scalars(
                        select(PlayerTaskState.task_id).where(PlayerTaskState.player_id == player_id)
                    )
                ).all()
            )
            assert task_ids == ("test.valid",)
        assert (await snapshot_store.read()).handler_ids == ("test.valid",)
        await runner.run()

        empty_catalogs = _registries().freeze(_FILE_IDS)
        with pytest.raises(TaskCatalogEmptyError):
            await TaskReconciliationRunner(
                session_factory,
                command_executor,
                empty_catalogs.tasks,
                TaskSnapshotStore(tmp_path / "empty-task-registry.json"),
            ).run()
        await engine.dispose()

    import asyncio

    asyncio.run(scenario())


def test_task_reconciliation_rolls_back_all_players_on_failure(tmp_path) -> None:
    async def scenario() -> None:
        async def valid_handler(_context) -> None:
            return None

        registries = _registries(("test.valid", valid_handler))
        catalogs = registries.freeze(_FILE_IDS)
        engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'reconcile-failure.sqlite3').as_posix()}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        player_ids = (uuid4(), uuid4())
        async with session_factory() as session:
            session.add_all(
                [
                    item
                    for player_id, username in zip(
                        player_ids,
                        ("reconcile-failure-one", "reconcile-failure-two"),
                        strict=True,
                    )
                    for item in (
                        PlayerRecord(id=player_id, username=username, username_normalized=username),
                        PlayerTaskState(player_id=player_id, task_id="test.stale", meta="{}"),
                    )
                ]
            )
            await session.commit()

        factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
        command_executor = CommandTransactionExecutor(factory, RequestCache(maxsize=4, ttl_seconds=60))
        execute_nocache_itx = command_executor.execute_nocache_itx
        calls = 0

        async def fail_on_second_player(session, player_id, operation, **kwargs) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("reconciliation failed")
            await execute_nocache_itx(session, player_id, operation, **kwargs)

        command_executor.execute_nocache_itx = fail_on_second_player
        snapshot_path = tmp_path / "reconcile-failure.json"
        runner = TaskReconciliationRunner(
            session_factory,
            command_executor,
            catalogs.tasks,
            TaskSnapshotStore(snapshot_path),
        )

        with pytest.raises(RuntimeError, match="reconciliation failed"):
            await runner.run()

        async with session_factory() as session:
            stale_count = len(
                (
                    await session.scalars(
                        select(PlayerTaskState).where(PlayerTaskState.task_id == "test.stale")
                    )
                ).all()
            )
            assert stale_count == 2
        assert not snapshot_path.exists()
        await engine.dispose()

    import asyncio

    asyncio.run(scenario())


def test_task_snapshot_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "task-registry.json"
    path.write_text("not-json", encoding="utf-8")

    async def scenario() -> None:
        with pytest.raises(TaskSnapshotError):
            await TaskSnapshotStore(path).read()

    import asyncio

    asyncio.run(scenario())


async def test_task_executor_runs_checkpoint_hook_inside_task_transaction(tmp_path) -> None:
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("start", ("saved",), is_entry=True))
    registries.progress.register(NormalProgressNode("saved", (), triggers_checkpoint=True))

    async def handler(context) -> None:
        context.player.progress.push("saved")

    registries.tasks.register("test.checkpoint", handler, dependencies=PlayerInterfaces.PROGRESS)
    catalogs = registries.freeze(_FILE_IDS)
    player_id = uuid4()
    entry_id = catalogs.progress.node_ids_by_str_id["start"]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        session.add_all(
            [
                PlayerRecord(id=player_id, username="checkpoint-task", username_normalized="checkpoint-task"),
                PlayerProgress(
                    player_id=player_id,
                    version=1,
                    unlocked_nodes=[PlayerProgressUnlockedNode(node_id=entry_id)],
                    frontier_nodes=[PlayerProgressFrontierNode(node_id=entry_id)],
                ),
                PlayerCredits(player_id=player_id),
                PlayerTaskState(player_id=player_id, task_id="test.checkpoint", meta="{}"),
            ]
        )
        await session.commit()
        factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
        hook = ProgressCheckpointHook(LocalCheckpointStore(tmp_path / "checkpoints"))
        executor = TaskExecutor(
            factory,
            catalogs.tasks,
            (hook,),
            pre_commit_interfaces=PlayerInterfaces.PROGRESS,
        )
        async with session.begin():
            await executor.run_itx(session, player_id)

        progress = await session.get(PlayerProgress, player_id)
        checkpoint = await session.get(PlayerProgressCheckpoint, (player_id, 0))
        assert progress is not None and progress.current_checkpoint_sequence == 0
        assert checkpoint is not None
        assert (tmp_path / "checkpoints" / checkpoint.storage_key).exists()
    await engine.dispose()


async def test_task_hook_failure_rolls_back_task_transaction(session) -> None:
    async def handler(_context) -> None:
        return None

    async def failing_hook(_session, _player) -> None:
        raise RuntimeError("hook failed")

    registries = _registries(("test.hook-failure", handler))
    player_id, _ = await _seed_player(session, task_ids=("test.hook-failure",))
    catalogs = registries.freeze(_FILE_IDS)
    factory = PlayerFactory(catalogs, FakeObjectStore(), _FILE_IDS)
    executor = TaskExecutor(factory, catalogs.tasks, (failing_hook,))

    with pytest.raises(RuntimeError, match="hook failed"):
        async with session.begin():
            await executor.run_itx(session, player_id)

    state = await session.get(PlayerTaskState, (player_id, "test.hook-failure"))
    assert state is not None and state.time_1 is None
