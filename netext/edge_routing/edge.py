from dataclasses import dataclass, field
from enum import Enum
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer
from typing import Iterable, Tuple

from netext.rendering.segment_buffer import ZIndex


@dataclass(frozen=True)
class EdgeInput:
    start: Point
    end: Point

    label: str | None

    routing_mode: EdgeRoutingMode
    edge_segment_drawing_mode: EdgeSegmentDrawingMode

    # This is used by the edge rasterizer to use data from
    # external layout engines where to route along.
    routing_hints: list[Point] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(
            (
                self.start,
                self.end,
                self.routing_mode,
                self.edge_segment_drawing_mode,
                frozenset(self.routing_hints),
            )
        )


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


@dataclass
class EdgePath:
    start: Point
    end: Point
    directed_points: list[Tuple[Point, Direction]]

    def cut_with_nodes(self, node_buffers: Iterable[NodeBuffer]) -> "EdgePath":
        cut_points = [
            (point, dir)
            for point, dir in self.directed_points
            if not any(node_buffer.shape.polygon(node_buffer).covers(point.shapely) for node_buffer in node_buffers)
        ]
        start = cut_points[0][0]
        end = cut_points[-1][0]
        return EdgePath(start=start, end=end, directed_points=cut_points)

    @property
    def points(self) -> list[Point]:
        return [
            point
            for i, (point, _) in enumerate(self.directed_points)
            if i == 0 or point != self.directed_points[i - 1][0]
        ]

    @property
    def min_bound(self) -> Point:
        return Point.min_point(self.points)

    @property
    def max_bound(self) -> Point:
        return Point.max_point(self.points)

    @property
    def length(self) -> int:
        return len(self.points)

    def edge_iter_point(self, index: int) -> Point:
        return self.points[index]


@dataclass(frozen=True)
class EdgeLayout:
    input: EdgeInput
    path: EdgePath
    z_index: ZIndex

    def __hash__(self) -> int:
        return hash(
            (
                self.input,
                self.z_index,
                frozenset(self.path.directed_points),
            )
        )

    @property
    def left_x(self) -> int:
        return min(point.x for point, _ in self.path.directed_points)

    @property
    def right_x(self) -> int:
        return max(point.x for point, _ in self.path.directed_points)

    @property
    def top_y(self) -> int:
        return min(point.y for point, _ in self.path.directed_points)

    @property
    def bottom_y(self) -> int:
        return max(point.y for point, _ in self.path.directed_points)
