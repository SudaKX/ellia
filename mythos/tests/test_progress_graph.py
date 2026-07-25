import pytest

from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.progress import (
    BranchProgressNode,
    BranchTargetResolutionError,
    MergeMode,
    MergeProgressNode,
    NormalProgressNode,
    ProgressRegistry,
)


def test_progress_graph_has_deterministic_ids_and_mappings() -> None:
    registry = ProgressRegistry()
    start = NormalProgressNode("start", ("finish",), is_entry=True)
    finish = NormalProgressNode("finish", ())
    registry.register(start)
    registry.register(finish)

    graph = registry.freeze()
    start_id = graph.node_ids_by_str_id["start"]
    finish_id = graph.node_ids_by_str_id["finish"]

    assert 0 < start_id < 1 << 63
    assert graph.str_ids_by_node_id[start_id] == "start"
    assert graph.node(start_id) is start
    assert graph.node_by_str_id("finish") is finish
    assert graph.successors_by_node_id[start_id] == (finish_id,)
    assert graph.predecessors_by_node_id[finish_id] == (start_id,)
    assert graph.entry_node_ids == (start_id,)
    with pytest.raises(RegistryFrozenError):
        registry.register(NormalProgressNode("later", ()))


def test_progress_structure_hash_is_registration_order_invariant() -> None:
    first = ProgressRegistry()
    second = ProgressRegistry()
    first_nodes = (
        NormalProgressNode("start", ("branch",), is_entry=True),
        BranchProgressNode("branch", ("left", "right"), lambda _: ("left",)),
        NormalProgressNode("left", ("merge",)),
        NormalProgressNode("right", ("merge",)),
        MergeProgressNode("merge", ("finish",), MergeMode.AND),
        NormalProgressNode("finish", ()),
    )
    second_nodes = (
        NormalProgressNode("start", ("branch",), is_entry=True, triggers_checkpoint=True),
        BranchProgressNode(
            "branch",
            ("right", "left"),
            lambda _: ("right",),
            triggers_checkpoint=True,
        ),
        NormalProgressNode("left", ("merge",), triggers_checkpoint=True),
        NormalProgressNode("right", ("merge",), triggers_checkpoint=True),
        MergeProgressNode("merge", ("finish",), MergeMode.OR, triggers_checkpoint=True),
        NormalProgressNode("finish", (), triggers_checkpoint=True),
    )
    for node in first_nodes:
        first.register(node)
    for node in reversed(second_nodes):
        second.register(node)

    first_graph = first.freeze()
    second_graph = second.freeze()

    assert first_graph.node_ids_by_str_id == second_graph.node_ids_by_str_id
    assert first_graph.structure_hash == second_graph.structure_hash


def test_branch_targets_resolve_to_declared_numeric_node_ids() -> None:
    registry = ProgressRegistry()
    registry.register(
        BranchProgressNode("start", ("left", "right"), lambda selected: (selected,), is_entry=True)
    )
    registry.register(NormalProgressNode("left", ()))
    registry.register(NormalProgressNode("right", ()))
    graph = registry.freeze()

    assert graph.resolve_branch_targets(graph.node_ids_by_str_id["start"], "right") == (
        graph.node_ids_by_str_id["right"],
    )


def test_valid_and_merge_graph() -> None:
    registry = ProgressRegistry()
    registry.register(NormalProgressNode("first", ("merge",), is_entry=True))
    registry.register(NormalProgressNode("second", ("merge",), is_entry=True))
    registry.register(MergeProgressNode("merge", ("finish",), MergeMode.AND))
    registry.register(NormalProgressNode("finish", ()))

    graph = registry.freeze()

    merge_id = graph.node_ids_by_str_id["merge"]
    assert len(graph.predecessors_by_node_id[merge_id]) == 2
    assert graph.node(merge_id).mode is MergeMode.AND


def test_progress_registry_rejects_duplicate_ids() -> None:
    registry = ProgressRegistry()
    registry.register(NormalProgressNode("start", (), is_entry=True))

    with pytest.raises(DuplicateStableIdError):
        registry.register(NormalProgressNode("start", ()))


@pytest.mark.parametrize(
    ("nodes", "message"),
    [
        (
            (
                NormalProgressNode("start", ("missing",), is_entry=True),
            ),
            "unknown node",
        ),
        (
            (
                NormalProgressNode("first", ("second",), is_entry=True),
                NormalProgressNode("second", ("first",)),
            ),
            "acyclic",
        ),
        (
            (
                NormalProgressNode("first", ("join",), is_entry=True),
                NormalProgressNode("second", ("join",), is_entry=True),
                NormalProgressNode("join", ()),
            ),
            "Only merge",
        ),
        (
            (
                NormalProgressNode("start", ()),
            ),
            "without predecessors must be entries",
        ),
    ],
)
def test_progress_graph_rejects_invalid_topology(
    nodes: tuple[NormalProgressNode, ...],
    message: str,
) -> None:
    registry = ProgressRegistry()
    for node in nodes:
        registry.register(node)

    with pytest.raises(RegistryError, match=message):
        registry.freeze()


@pytest.mark.parametrize(
    "selector",
    [
        lambda _: ["left"],
        lambda _: ("missing",),
        lambda _: ("left", "left"),
    ],
)
def test_branch_target_resolution_rejects_invalid_outputs(selector) -> None:
    registry = ProgressRegistry()
    registry.register(BranchProgressNode("start", ("left",), selector, is_entry=True))
    registry.register(NormalProgressNode("left", ()))
    graph = registry.freeze()

    with pytest.raises(BranchTargetResolutionError):
        graph.resolve_branch_targets(graph.node_ids_by_str_id["start"], None)
