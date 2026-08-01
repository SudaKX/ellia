from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any

from mythos.registry.errors import RegistryError
from mythos.registry.progress.definitions import (
    BranchProgressNode,
    MergeProgressNode,
    NormalProgressNode,
    ProgressNode,
)

_NODE_ID_DOMAIN = b"mythos.progress.node-id.v1\0"
_MAX_SIGNED_63_BIT_INTEGER = (1 << 63) - 1
_STRUCTURE_FORMAT = 1


class ProgressGraphError(RegistryError):
    pass


class ProgressNodeIdCollisionError(ProgressGraphError):
    pass


class ProgressNodeNotFoundError(ProgressGraphError):
    pass


class BranchTargetResolutionError(ProgressGraphError):
    pass


def derive_progress_node_id(str_id: str) -> int:
    digest = hashlib.sha256(_NODE_ID_DOMAIN + str_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") % _MAX_SIGNED_63_BIT_INTEGER + 1


class ProgressGraph:
    def __init__(
        self,
        *,
        node_ids_by_str_id: Mapping[str, int],
        str_ids_by_node_id: Mapping[int, str],
        nodes_by_node_id: Mapping[int, ProgressNode],
        successors_by_node_id: Mapping[int, tuple[int, ...]],
        predecessors_by_node_id: Mapping[int, tuple[int, ...]],
        entry_node_ids: tuple[int, ...],
        structure_hash: str,
    ) -> None:
        self.node_ids_by_str_id = dict(node_ids_by_str_id)
        self.str_ids_by_node_id = dict(str_ids_by_node_id)
        self.nodes_by_node_id = dict(nodes_by_node_id)
        self.successors_by_node_id = dict(successors_by_node_id)
        self.predecessors_by_node_id = dict(predecessors_by_node_id)
        self.entry_node_ids = entry_node_ids
        self.structure_hash = structure_hash

    @classmethod
    def build(cls, nodes_by_str_id: Mapping[str, ProgressNode]) -> ProgressGraph:
        ordered_nodes = tuple(sorted(nodes_by_str_id.items()))
        node_ids_by_str_id: dict[str, int] = {}
        str_ids_by_node_id: dict[int, str] = {}
        nodes_by_node_id: dict[int, ProgressNode] = {}

        for str_id, node in ordered_nodes:
            node_id = derive_progress_node_id(str_id)
            existing_str_id = str_ids_by_node_id.get(node_id)
            if existing_str_id is not None:
                raise ProgressNodeIdCollisionError(
                    f"Progress node IDs collide for {existing_str_id!r} and {str_id!r}."
                )
            node_ids_by_str_id[str_id] = node_id
            str_ids_by_node_id[node_id] = str_id
            nodes_by_node_id[node_id] = node

        successors_by_node_id: dict[int, tuple[int, ...]] = {}
        mutable_predecessors: dict[int, list[int]] = {
            node_id: [] for node_id in nodes_by_node_id
        }
        for str_id, node in ordered_nodes:
            if len(set(node.next)) != len(node.next):
                raise ProgressGraphError(f"Progress node {str_id!r} has duplicate edges.")
            if str_id in node.next:
                raise ProgressGraphError(f"Progress node {str_id!r} cannot target itself.")

            successor_ids: list[int] = []
            for target_str_id in node.next:
                try:
                    target_node_id = node_ids_by_str_id[target_str_id]
                except KeyError as error:
                    raise ProgressGraphError(
                        f"Progress node {str_id!r} targets unknown node {target_str_id!r}."
                    ) from error
                successor_ids.append(target_node_id)
                mutable_predecessors[target_node_id].append(node_ids_by_str_id[str_id])
            successors_by_node_id[node_ids_by_str_id[str_id]] = tuple(successor_ids)

        predecessors_by_node_id = {
            node_id: tuple(predecessors)
            for node_id, predecessors in mutable_predecessors.items()
        }
        cls._validate_node_degrees(nodes_by_node_id, successors_by_node_id, predecessors_by_node_id)
        cls._validate_dag(successors_by_node_id, predecessors_by_node_id)
        entry_node_ids = cls._validate_entries(
            nodes_by_node_id,
            successors_by_node_id,
            predecessors_by_node_id,
        )

        return cls(
            node_ids_by_str_id=node_ids_by_str_id,
            str_ids_by_node_id=str_ids_by_node_id,
            nodes_by_node_id=nodes_by_node_id,
            successors_by_node_id=successors_by_node_id,
            predecessors_by_node_id=predecessors_by_node_id,
            entry_node_ids=entry_node_ids,
            structure_hash=_structure_hash(ordered_nodes),
        )

    def node(self, node_id: int) -> ProgressNode:
        try:
            return self.nodes_by_node_id[node_id]
        except KeyError as error:
            raise ProgressNodeNotFoundError("Progress node not found.") from error

    def node_by_id(self, node_id: int) -> ProgressNode:
        return self.node(node_id)

    def node_by_str_id(self, str_id: str) -> ProgressNode:
        try:
            node_id = self.node_ids_by_str_id[str_id]
        except KeyError as error:
            raise ProgressNodeNotFoundError("Progress node not found.") from error
        return self.node(node_id)

    def resolve_branch_targets(self, branch_node_id: int, branch_arg: Any) -> tuple[int, ...]:
        node = self.node(branch_node_id)
        if not isinstance(node, BranchProgressNode):
            raise BranchTargetResolutionError("Progress node is not a branch node.")
        try:
            selected_str_ids = node.how(branch_arg)
        except Exception as error:
            raise BranchTargetResolutionError("Branch target selector failed.") from error
        if not isinstance(selected_str_ids, tuple) or any(
            not isinstance(str_id, str) for str_id in selected_str_ids
        ):
            raise BranchTargetResolutionError("Branch target selectors must return tuple[str, ...].")
        if len(set(selected_str_ids)) != len(selected_str_ids):
            raise BranchTargetResolutionError("Branch target selectors cannot select a target twice.")
        declared_targets = set(node.next)
        if any(str_id not in declared_targets for str_id in selected_str_ids):
            raise BranchTargetResolutionError("Branch target selector chose an undeclared target.")
        return tuple(self.node_ids_by_str_id[str_id] for str_id in selected_str_ids)

    @staticmethod
    def _validate_node_degrees(
        nodes_by_node_id: Mapping[int, ProgressNode],
        successors_by_node_id: Mapping[int, tuple[int, ...]],
        predecessors_by_node_id: Mapping[int, tuple[int, ...]],
    ) -> None:
        for node_id, node in nodes_by_node_id.items():
            successor_count = len(successors_by_node_id[node_id])
            predecessor_count = len(predecessors_by_node_id[node_id])
            if isinstance(node, MergeProgressNode):
                if predecessor_count < 2:
                    raise ProgressGraphError("Merge progress nodes require at least two predecessors.")
                if successor_count > 1:
                    raise ProgressGraphError("Merge progress nodes can have at most one successor.")
            elif isinstance(node, NormalProgressNode):
                if predecessor_count > 1:
                    raise ProgressGraphError("Only merge progress nodes can have multiple predecessors.")
                if successor_count > 1:
                    raise ProgressGraphError("Normal progress nodes can have at most one successor.")
            elif predecessor_count > 1:
                raise ProgressGraphError("Only merge progress nodes can have multiple predecessors.")

    @staticmethod
    def _validate_dag(
        successors_by_node_id: Mapping[int, tuple[int, ...]],
        predecessors_by_node_id: Mapping[int, tuple[int, ...]],
    ) -> None:
        remaining_predecessors = {
            node_id: len(predecessors)
            for node_id, predecessors in predecessors_by_node_id.items()
        }
        pending = sorted(
            node_id for node_id, count in remaining_predecessors.items() if count == 0
        )
        visited_count = 0
        while pending:
            node_id = pending.pop()
            visited_count += 1
            for successor_id in successors_by_node_id[node_id]:
                remaining_predecessors[successor_id] -= 1
                if remaining_predecessors[successor_id] == 0:
                    pending.append(successor_id)
        if visited_count != len(successors_by_node_id):
            raise ProgressGraphError("Progress graph must be acyclic.")

    @staticmethod
    def _validate_entries(
        nodes_by_node_id: Mapping[int, ProgressNode],
        successors_by_node_id: Mapping[int, tuple[int, ...]],
        predecessors_by_node_id: Mapping[int, tuple[int, ...]],
    ) -> tuple[int, ...]:
        entry_node_ids = tuple(
            node_id for node_id, node in nodes_by_node_id.items() if node.is_entry
        )
        for node_id in entry_node_ids:
            if predecessors_by_node_id[node_id]:
                raise ProgressGraphError("Progress entry nodes cannot have predecessors.")

        root_node_ids = tuple(
            node_id
            for node_id, predecessors in predecessors_by_node_id.items()
            if not predecessors
        )
        if set(root_node_ids) != set(entry_node_ids):
            raise ProgressGraphError("All progress nodes without predecessors must be entries.")

        reachable_node_ids = set(entry_node_ids)
        pending = list(entry_node_ids)
        while pending:
            node_id = pending.pop()
            for successor_id in successors_by_node_id[node_id]:
                if successor_id not in reachable_node_ids:
                    reachable_node_ids.add(successor_id)
                    pending.append(successor_id)
        if len(reachable_node_ids) != len(nodes_by_node_id):
            raise ProgressGraphError("All progress nodes must be reachable from entries.")
        return entry_node_ids


def _structure_hash(nodes: tuple[tuple[str, ProgressNode], ...]) -> str:
    topology = {
        "format": _STRUCTURE_FORMAT,
        "nodes": [
            {"id": str_id, "next": sorted(node.next)}
            for str_id, node in nodes
        ],
    }
    encoded = json.dumps(
        topology,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
