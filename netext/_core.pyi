from collections.abc import Hashable
from enum import Enum
from typing import Any, Iterable, Iterator


class CoreGraph:
    ...
    @classmethod
    def from_edges(cls, edges: list[tuple[Hashable, Hashable]]) -> CoreGraph:
        ...

    def contains_node(self, node: Hashable) -> bool:
        ...

    def contains_edge(self, u: Hashable, v: Hashable) -> bool:
        ...

    def add_node(self, node: Hashable, data: dict[str, Any]) -> None:
        ...

    def add_edge(self, u: Hashable, v: Hashable, data: dict[str, Any]) -> None:
        ...

    def update_node_data(self, node: Hashable, data: dict[str, Any]) -> None:
        ...

    def all_edges(self) -> Iterable[tuple[Hashable, Hashable]]:
        ...

    def all_nodes(self) -> Iterable[Hashable]:
        ...

    def remove_node(self, node: Hashable) -> None:
        ...

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        ...

    def edge_data(self, u: Hashable, v: Hashable) -> dict[str, Any]:
        ...

    def edge_data_or_default(self, u: Hashable, v: Hashable, default: dict[str, Any]) -> dict[str, Any]:
        ...

    def node_data_or_default(self, node: Hashable, default: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_edge_data(self, u: Hashable, v: Hashable, data: dict[str, Any]) -> None:
        ...

    def update_node_size(self, node: Hashable, size: Size) -> None:
        ...

    def neighbors(self, node: Hashable) -> Iterator[Hashable]:
        ...

    def neighbors_outgoing(self, node: Hashable) -> Iterator[Hashable]:
        ...

    def neighbors_incoming(self, node: Hashable) -> Iterator[Hashable]:
        ...


class Point:
    x: int
    y: int

    def __init__(self, x: int, y: int) -> None:
        ...

class Size:
    def __init__(self, width: int, height: int) -> None:
        ...

class RectangularNode:
    def __init__(self, size: Size) -> None:
        ...

class PlacedRectangularNode:
    def __init__(self, center: Point, node: RectangularNode) -> None:
        ...


class EdgeRouter:
    def add_node(self, node: Hashable, placed_node: PlacedRectangularNode) -> None:
        ...

    def remove_node(self, node: Hashable) -> None:
        ...

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        ...


class Direction(Enum):
    CENTER = -1
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    UP_RIGHT = 4
    UP_LEFT = 5
    DOWN_RIGHT = 6
    DOWN_LEFT = 7

class LayoutEngine:
    def layout(self, graph: CoreGraph) -> Iterable[tuple[Hashable, Point]]:
        ...

class SugiyamaLayout(LayoutEngine):
    ...
