from collections.abc import Hashable
from typing import Generic, TypeVar

from networkx import Graph, DiGraph

from netext.geometry.point import FloatPoint

G = TypeVar("G", Graph, DiGraph)


class LayoutEngine(Generic[G]):
    def __call__(self, graph: G) -> dict[Hashable, FloatPoint]:
        return NotImplemented  # pragma: no cover
