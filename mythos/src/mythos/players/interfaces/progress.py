from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mythos.persistence.models import (
    PlayerProgress,
    PlayerProgressFrontierNode,
    PlayerProgressUnlockedNode,
)
from mythos.registry.progress import BranchProgressNode, MergeMode, MergeProgressNode, ProgressNodeNotFoundError

if TYPE_CHECKING:
    from mythos.registry.bundle import RuntimeCatalogs


class ReadOnlyPlayerError(Exception):
    pass


class ProgressTransitionError(Exception):
    pass


class ProgressInterface:
    def __init__(
        self,
        progress: PlayerProgress,
        *,
        writable: bool,
        catalogs: RuntimeCatalogs,
    ) -> None:
        self._progress = progress
        self._writable = writable
        self._catalogs = catalogs

    @property
    def current_account(self) -> str:
        return self._progress.current_account

    @property
    def unlocked_node_ids(self) -> frozenset[int]:
        return frozenset(node.node_id for node in self._progress.unlocked_nodes)

    @property
    def frontier_node_ids(self) -> frozenset[int]:
        return frozenset(node.node_id for node in self._progress.frontier_nodes)

    @property
    def current_checkpoint_sequence(self) -> int:
        return self._progress.current_checkpoint_sequence

    @property
    def next_checkpoint_sequence(self) -> int:
        return self._progress.next_checkpoint_sequence

    @property
    def version(self) -> int:
        return self._progress.version

    def push(self, id: str, branch_arg: Any | None = None) -> None:
        if not self._writable:
            raise ReadOnlyPlayerError("Read-only players cannot modify progress.")
        graph = self._catalogs.progress
        try:
            node_id = graph.node_ids_by_str_id[id]
        except KeyError as error:
            raise ProgressTransitionError("Progress node not found.") from error

        node = graph.node(node_id)
        newly_unlocked: set[int] = set()
        if isinstance(node, MergeProgressNode):
            raise ProgressTransitionError("Merge progress nodes advance automatically.")
        if isinstance(node, BranchProgressNode) and branch_arg is not None:
            self._advance_branch(node_id, branch_arg, newly_unlocked)
        else:
            if branch_arg is not None:
                raise ProgressTransitionError("Only branch progress nodes accept an argument.")
            self._advance_to(node_id, newly_unlocked)

        self._resolve_merges(newly_unlocked)
        self._progress.version += 1

    def _advance_to(self, node_id: int, newly_unlocked: set[int]) -> None:
        if node_id in self.unlocked_node_ids:
            raise ProgressTransitionError("Progress nodes cannot be unlocked twice.")
        predecessors = self._catalogs.progress.predecessors_by_node_id[node_id]
        active_predecessors = set(predecessors).intersection(self.frontier_node_ids)
        if len(predecessors) != 1 or len(active_predecessors) != 1:
            raise ProgressTransitionError("Progress node is not reachable from the current frontier.")
        self._remove_frontier(active_predecessors)
        self._unlock(node_id, newly_unlocked)

    def _advance_branch(self, node_id: int, branch_arg: Any, newly_unlocked: set[int]) -> None:
        if node_id not in self.frontier_node_ids:
            raise ProgressTransitionError("Branch progress node is not waiting at the frontier.")
        try:
            target_ids = self._catalogs.progress.resolve_branch_targets(node_id, branch_arg)
        except ProgressNodeNotFoundError as error:
            raise ProgressTransitionError("Branch progress node not found.") from error
        except Exception as error:
            raise ProgressTransitionError("Branch progress node rejected its targets.") from error
        if any(target_id in self.unlocked_node_ids for target_id in target_ids):
            raise ProgressTransitionError("Branch progress node selected an unlocked target.")
        self._remove_frontier({node_id})
        for target_id in target_ids:
            target = self._catalogs.progress.node(target_id)
            if isinstance(target, MergeProgressNode):
                raise ProgressTransitionError("Branches cannot directly select merge progress nodes.")
            self._unlock(target_id, newly_unlocked)

    def _resolve_merges(self, newly_unlocked: set[int]) -> None:
        graph = self._catalogs.progress
        while True:
            frontier_ids = self.frontier_node_ids
            candidates = {
                successor_id
                for frontier_id in frontier_ids
                for successor_id in graph.successors_by_node_id[frontier_id]
                if isinstance(graph.node(successor_id), MergeProgressNode)
            }
            resolved = False
            for merge_id in sorted(candidates):
                merge = graph.node(merge_id)
                assert isinstance(merge, MergeProgressNode)
                predecessors = set(graph.predecessors_by_node_id[merge_id])
                active_predecessors = predecessors.intersection(frontier_ids)
                if merge.mode is MergeMode.AND:
                    is_ready = active_predecessors == predecessors
                    consumed = predecessors
                else:
                    is_ready = bool(active_predecessors)
                    consumed = active_predecessors
                if not is_ready:
                    continue
                if merge_id in self.unlocked_node_ids:
                    raise ProgressTransitionError("Merge progress node resolved more than once.")
                self._remove_frontier(consumed)
                self._unlock(merge_id, newly_unlocked)
                resolved = True
                break
            if not resolved:
                return

    def _unlock(self, node_id: int, newly_unlocked: set[int]) -> None:
        self._progress.unlocked_nodes.append(PlayerProgressUnlockedNode(node_id=node_id))
        self._progress.frontier_nodes.append(PlayerProgressFrontierNode(node_id=node_id))
        newly_unlocked.add(node_id)

    def _remove_frontier(self, node_ids: set[int]) -> None:
        self._progress.frontier_nodes[:] = [
            node for node in self._progress.frontier_nodes if node.node_id not in node_ids
        ]
