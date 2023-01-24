from collections.abc import Hashable
from typing import Generic, TypeVar

from networkx.classes.graph import Graph, DiGraph

G = TypeVar("G", Graph, DiGraph)


class LayoutEngine(Generic[G]):
    def __call__(self, graph: G) -> dict[Hashable, tuple[float, float]]:
        return NotImplemented  # pragma: no cover
