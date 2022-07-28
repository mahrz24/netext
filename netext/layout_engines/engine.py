from typing import Dict, Generic, Hashable, Tuple, TypeVar

import networkx as nx

G = TypeVar("G", nx.Graph, nx.DiGraph)


class LayoutEngine(Generic[G]):
    def __call__(self, graph: G) -> Dict[Hashable, Tuple[float, float]]:
        return NotImplemented
