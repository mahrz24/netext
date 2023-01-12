from collections.abc import Hashable
from typing import Generic, TypeVar

import networkx as nx

G = TypeVar("G", nx.Graph, nx.DiGraph)


class LayoutEngine(Generic[G]):
    def __call__(self, graph: G) -> dict[Hashable, tuple[float, float]]:
        return NotImplemented  # pragma: no cover
