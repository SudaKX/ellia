from __future__ import annotations

from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.progress.definitions import (
    BranchProgressNode,
    MergeMode,
    MergeProgressNode,
    NormalProgressNode,
    ProgressNode,
)
from mythos.registry.progress.graph import ProgressGraph


class ProgressRegistry:
    def __init__(self) -> None:
        self._nodes_by_str_id: dict[str, ProgressNode] = {}
        self._frozen = False
        self._graph: ProgressGraph | None = None

    def register(self, node: ProgressNode) -> None:
        if self._frozen:
            raise RegistryFrozenError("The progress registry is frozen.")
        self._validate_node(node)
        if node.id in self._nodes_by_str_id:
            raise DuplicateStableIdError(node.id)
        self._nodes_by_str_id[node.id] = node

    def freeze(self) -> ProgressGraph:
        if self._graph is not None:
            return self._graph
        graph = ProgressGraph.build(self._nodes_by_str_id)
        self._frozen = True
        self._graph = graph
        return graph

    @staticmethod
    def _validate_node(node: ProgressNode) -> None:
        if not isinstance(node, (NormalProgressNode, BranchProgressNode, MergeProgressNode)):
            raise RegistryError("Progress registrations must be progress nodes.")
        if not isinstance(node.id, str) or not node.id:
            raise RegistryError("Progress nodes require a non-empty string ID.")
        if not isinstance(node.next, tuple) or any(
            not isinstance(target, str) or not target for target in node.next
        ):
            raise RegistryError("Progress node targets must be non-empty string IDs in a tuple.")
        if type(node.is_entry) is not bool or type(node.triggers_checkpoint) is not bool:
            raise RegistryError("Progress node flags must be booleans.")
        if isinstance(node, BranchProgressNode) and not callable(node.how):
            raise RegistryError("Branch progress nodes require a target selector.")
        if isinstance(node, MergeProgressNode) and not isinstance(node.mode, MergeMode):
            raise RegistryError("Merge progress nodes require a merge mode.")
