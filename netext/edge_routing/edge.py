from dataclasses import dataclass, field
from enum import Enum
import itertools
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Point
from netext.geometry.line_segment import LineSegment
from netext.node_rasterizer import NodeBuffer

from shapely import LineString


from typing import Iterable, Iterator, Tuple

from netext.rendering.segment_buffer import ZIndex


class EdgeSegment(LineSegment):
    def intersects_with_node(self, node_buffer: NodeBuffer) -> bool:
        direct_line = LineString([self.start.shapely, self.end.shapely])
        node_polygon = node_buffer.shape.polygon(node_buffer)
        intersection = direct_line.intersection(node_polygon)
        return not intersection.is_empty

    def intersects_with_edge_segment(self, other: "EdgeSegment") -> int:
        direct_line = LineString([self.start.shapely, self.end.shapely])
        other_direct_line = LineString([other.start.shapely, other.end.shapely])
        intersection = direct_line.intersection(other_direct_line)
        if intersection.is_empty:
            return 0
        else:
            return int(intersection.length)

    def cut_multiple(self, node_buffers: Iterator[NodeBuffer]) -> list["EdgeSegment"]:
        node_buffer: NodeBuffer | None = next(node_buffers, None)
        if node_buffer is None:
            return [self]
        else:
            return list(
                itertools.chain(*[edge_segment.cut_multiple(node_buffers) for edge_segment in self.cut(node_buffer)])
            )

    def cut(self, node_buffer: NodeBuffer) -> list["EdgeSegment"]:
        node_shape = node_buffer.shape.polygon(shape_buffer=node_buffer, margin=0.75)
        result = []
        if self.shapely.intersects(node_shape):
            remaining = self.shapely.difference(node_shape)
            if remaining.is_empty:
                return []
            if remaining.geom_type == "MultiLineString":
                for line in remaining.geoms:
                    result.append(
                        EdgeSegment(
                            start=Point.from_shapely(line.interpolate(0, normalized=True)),
                            end=Point.from_shapely(line.interpolate(1, normalized=True)),
                            _parent=self.parent,
                        )
                    )
            else:
                result.append(
                    EdgeSegment(
                        start=Point.from_shapely(remaining.interpolate(0, normalized=True)),
                        end=Point.from_shapely(remaining.interpolate(1, normalized=True)),
                        _parent=self.parent,
                    )
                )
            return result
        return [self]

    def count_node_intersections(self, node_buffers: Iterable[NodeBuffer]) -> int:
        return sum(1 for node_buffer in node_buffers if self.intersects_with_node(node_buffer))

    def count_edge_intersections(self, edges: Iterable["EdgeLayout"]) -> int:
        return sum(self.intersects_with_edge_segment(segment) for edge in edges for segment in edge.segments)

    def ortho_split_x(self) -> list["EdgeSegment"]:
        if self.start.x == self.end.x or self.start.y == self.end.y:
            return [self]
        else:
            return [
                EdgeSegment(start=self.start, end=Point(x=self.start.x, y=self.end.y)),
                EdgeSegment(start=Point(x=self.start.x, y=self.end.y), end=self.end),
            ]

    def ortho_split_y(self) -> list["EdgeSegment"]:
        if self.start.x == self.end.x or self.start.y == self.end.y:
            return [self]
        else:
            return [
                EdgeSegment(start=self.start, end=Point(x=self.end.x, y=self.start.y)),
                EdgeSegment(start=Point(x=self.end.x, y=self.start.y), end=self.end),
            ]


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
    points: list[Tuple[Point, Direction]]

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
                frozenset(self.path.points),
            )
        )

    @property
    def left_x(self) -> int:
        return min(point.x for point, _ in self.path.points)

    @property
    def right_x(self) -> int:
        return max(point.x for point, _ in self.path.points)

    @property
    def top_y(self) -> int:
        return min(point.y for point, _ in self.path.points)

    @property
    def bottom_y(self) -> int:
        return max(point.y for point, _ in self.path.points)





@dataclass
class RoutedEdgeSegments:
    segments: list[EdgeSegment]
    intersections: int

    @classmethod
    def from_segments_compute_intersections(
        cls,
        segments: list[EdgeSegment],
        node_buffers: Iterable[NodeBuffer],
        edges: Iterable[EdgeLayout] = [],
    ) -> "RoutedEdgeSegments":
        return cls(
            segments=segments,
            intersections=sum(segment.count_node_intersections(node_buffers) for segment in segments)
            + sum(segment.count_edge_intersections(edges) for segment in segments),
        )

    def concat(self, other: "RoutedEdgeSegments") -> "RoutedEdgeSegments":
        return RoutedEdgeSegments(
            segments=self.segments + other.segments,
            intersections=self.intersections + other.intersections,
        )

    def cut_with_nodes(self, node_buffers: Iterable[NodeBuffer]) -> "RoutedEdgeSegments":
        # We remove any edge segments that were cut to a single point.
        return RoutedEdgeSegments(
            segments=list(itertools.chain(*[segment.cut_multiple(iter(node_buffers)) for segment in self.segments])),
            intersections=self.intersections,
        )

    @property
    def min_bound(self) -> Point:
        return Point.min_point([edge_segment.min_bound for edge_segment in self.segments])

    @property
    def max_bound(self) -> Point:
        return Point.max_point([edge_segment.max_bound for edge_segment in self.segments])

    @property
    def length(self) -> int:
        return sum(segment.length for segment in self.segments)

    def edge_iter_point(self, index: int) -> Point:
        # Return the point traversing the whole edge over all segments.
        iter_reversed = index < 0
        # The index is the index of the point in the whole edge.
        segments = iter(self.segments)
        if iter_reversed:
            segments = reversed(self.segments)
            index = -index - 1
        for segment in segments:
            if index <= segment.length:
                return segment.interpolate(index, reversed=iter_reversed)
            else:
                index -= segment.length

        if iter_reversed:
            return self.segments[0].start
        return self.segments[-1].end
