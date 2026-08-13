from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias


BranchTargetSelector: TypeAlias = Callable[[Any], tuple[str, ...]]


class MergeMode(Enum):
    AND = "and"
    OR = "or"


@dataclass(frozen=True)
class NormalProgressNode:
    id: str
    next: tuple[str, ...]
    is_entry: bool = False
    triggers_checkpoint: bool = False


@dataclass(frozen=True)
class BranchProgressNode:
    id: str
    next: tuple[str, ...]
    how: BranchTargetSelector
    is_entry: bool = False
    triggers_checkpoint: bool = False


@dataclass(frozen=True)
class MergeProgressNode:
    id: str
    next: tuple[str, ...]
    mode: MergeMode
    is_entry: bool = False
    triggers_checkpoint: bool = False


ProgressNode: TypeAlias = NormalProgressNode | BranchProgressNode | MergeProgressNode
