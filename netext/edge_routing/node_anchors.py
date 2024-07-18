from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass, field
from netext._core import Direction
from netext.geometry.magnet import ShapeSide
from netext.geometry.point import Point

@dataclass
class NodeAnchors:
    port_sides: dict[str, ShapeSide]
    edge_sides: dict[Hashable, ShapeSide]

    port_positions: dict[str, Point]
    all_positions: dict[str | Hashable, tuple[Point, Direction]]

    ports_per_side: dict[ShapeSide, list[str]] = field(default_factory=lambda: defaultdict(list))
    edges_per_side: dict[ShapeSide, list[Hashable]] = field(default_factory=lambda: defaultdict(list))
