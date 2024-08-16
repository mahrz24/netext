from dataclasses import dataclass
from enum import Enum
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Point
from typing import Tuple


@dataclass(frozen=True)
class EdgeInput:
    start: Point
    end: Point

    label: str | None

    routing_mode: EdgeRoutingMode
    edge_segment_drawing_mode: EdgeSegmentDrawingMode

    def __hash__(self) -> int:
        return hash(
            (
                self.start,
                self.end,
                self.routing_mode,
                self.edge_segment_drawing_mode,
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
