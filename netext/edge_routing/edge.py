from dataclasses import dataclass
from functools import cached_property
from netext._core import DirectedPoint, Point
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode


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

@dataclass(frozen=True)
class EdgePath:
    start: Point
    end: Point
    directed_points: list[DirectedPoint]

    @cached_property
    def distinct_points(self) -> list[Point]:
        return [
            directed_point.point
            for i, directed_point in enumerate(self.directed_points)
            if i == 0 or directed_point.point != self.directed_points[i - 1].point
        ]

    @property
    def min_bound(self) -> Point:
        return Point.min_point(self.distinct_points)

    @property
    def max_bound(self) -> Point:
        return Point.max_point(self.distinct_points)

    @property
    def length(self) -> int:
        return len(self.distinct_points)
