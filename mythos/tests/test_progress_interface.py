from uuid import uuid4

import pytest

from mythos.persistence.models import PlayerProgress, PlayerProgressFrontierNode, PlayerProgressUnlockedNode
from mythos.players.interfaces import ProgressInterface, ProgressTransitionError
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import BranchProgressNode, MergeMode, MergeProgressNode, NormalProgressNode


def _interface(registries: RegistryBundle) -> ProgressInterface:
    catalogs = registries.freeze(_file_ids())
    entry_ids = catalogs.progress.entry_node_ids
    progress = PlayerProgress(
        player_id=uuid4(),
        current_account="PLAYER",
        version=1,
        unlocked_nodes=[PlayerProgressUnlockedNode(node_id=node_id) for node_id in entry_ids],
        frontier_nodes=[PlayerProgressFrontierNode(node_id=node_id) for node_id in entry_ids],
    )
    return ProgressInterface(progress, writable=True, catalogs=catalogs)


def _file_ids():
    from mythos.core.file_ids import FileIdCodec

    return FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


def test_status_queries_resolve_registered_string_ids() -> None:
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("start", ("finish",), is_entry=True))
    registries.progress.register(NormalProgressNode("finish", ()))
    interface = _interface(registries)

    assert interface.is_unlocked("start")
    assert interface.is_frontier("start")
    assert not interface.is_unlocked("finish")
    assert not interface.is_frontier("finish")
    assert not interface.is_unlocked("missing")
    assert not interface.is_frontier("missing")

    interface.push("finish")

    assert interface.is_unlocked("start")
    assert not interface.is_frontier("start")
    assert interface.is_unlocked("finish")
    assert interface.is_frontier("finish")


def test_push_advances_branch_and_resolves_and_merge() -> None:
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("start", ("branch",), is_entry=True))
    registries.progress.register(BranchProgressNode("branch", ("left", "right"), lambda _: ("left", "right")))
    registries.progress.register(NormalProgressNode("left", ("merge",)))
    registries.progress.register(NormalProgressNode("right", ("merge",)))
    registries.progress.register(MergeProgressNode("merge", ("finish",), MergeMode.AND))
    registries.progress.register(NormalProgressNode("finish", ()))
    interface = _interface(registries)
    graph = interface._catalogs.progress

    interface.push("branch")
    assert interface.frontier_node_ids == {graph.node_ids_by_str_id["branch"]}

    interface.push("branch", {"paths": ["left", "right"]})
    assert interface.frontier_node_ids == {graph.node_ids_by_str_id["merge"]}
    assert interface.version == 3

    with pytest.raises(ProgressTransitionError, match="advance automatically"):
        interface.push("merge")

    interface.push("finish")
    assert interface.frontier_node_ids == {graph.node_ids_by_str_id["finish"]}


def test_push_rejects_unreachable_nodes_and_direct_merges() -> None:
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("first", ("merge",), is_entry=True))
    registries.progress.register(NormalProgressNode("second", ("merge",), is_entry=True))
    registries.progress.register(MergeProgressNode("merge", (), MergeMode.AND))
    interface = _interface(registries)

    with pytest.raises(ProgressTransitionError, match="advance automatically"):
        interface.push("merge")
    with pytest.raises(ProgressTransitionError, match="not found"):
        interface.push("missing")
