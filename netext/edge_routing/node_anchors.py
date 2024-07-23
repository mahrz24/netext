from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass, field
from netext._core import Direction
from netext.geometry.magnet import ShapeSide
from netext.geometry.point import Point

@dataclass
class NodeAnchors:
    port_sides: dict[str, ShapeSide] = field(default_factory=dict)
    edge_sides: dict[Hashable, ShapeSide] = field(default_factory=dict)

    port_positions: dict[str, Point] = field(default_factory=dict)
    all_positions: dict[str | Hashable, tuple[Point, Direction]] = field(default_factory=dict)

    ports_per_side: dict[ShapeSide, list[str]] = field(default_factory=lambda: defaultdict(list))
    edges_per_side: dict[ShapeSide, list[Hashable]] = field(default_factory=lambda: defaultdict(list))
