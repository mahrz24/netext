from dataclasses import dataclass, field
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Point
from netext.geometry.line_segment import LineSegment
from netext.node_rasterizer import NodeBuffer


from shapely import LineString


from typing import Iterable, Iterator


class EdgeSegment(LineSegment):
    def intersects_with_node(self, node_buffer: NodeBuffer) -> bool:
        direct_line = LineString([self.start.shapely, self.end.shapely])
        node_polygon = node_buffer.shape.bounding_box(node_buffer)
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

    def cut_multiple(self, node_buffers: Iterator[NodeBuffer]) -> "EdgeSegment":
        node_buffer: NodeBuffer | None = next(node_buffers, None)
        if node_buffer is None:
            return self
        else:
            return self.cut(node_buffer).cut_multiple(node_buffers)

    def cut(self, node_buffer: NodeBuffer) -> "EdgeSegment":
        node_shape = node_buffer.shape.bounding_box(node_buffer=node_buffer, margin=1)

        if self.shapely.intersects(node_shape):
            remaining: LineString = self.shapely.difference(node_shape)
            if remaining.is_empty or remaining.geom_type == "MultiLine":
                # The line segment is fully ocluded by the node or cut into two we keep it as it is
                # TODO fix to make this return a list, so we cut return none or multiple segments
                return self
            return EdgeSegment(
                start=Point.from_shapely(remaining.interpolate(0, normalized=True)),
                end=Point.from_shapely(remaining.interpolate(1, normalized=True)),
            )
        return self

    def count_node_intersections(self, node_buffers: Iterable[NodeBuffer]) -> int:
        return sum(
            1 for node_buffer in node_buffers if self.intersects_with_node(node_buffer)
        )

    def count_edge_intersections(self, edges: Iterable["EdgeLayout"]) -> int:
        return sum(
            self.intersects_with_edge_segment(segment)
            for edge in edges
            for segment in edge.segments
        )

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


@dataclass
class EdgeInput:
    start: Point
    end: Point

    # label: str | None

    routing_mode: EdgeRoutingMode
    edge_segment_drawing_mode: EdgeSegmentDrawingMode

    # This is used by the edge rasterizer to use data from
    # external layout engines where to route along.
    routing_hints: list[Point] = field(default_factory=list)


@dataclass
class EdgeLayout:
    input: EdgeInput
    segments: list[EdgeSegment]


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
            intersections=sum(
                segment.count_node_intersections(node_buffers) for segment in segments
            )
            + sum(segment.count_edge_intersections(edges) for segment in segments),
        )

    def concat(self, other: "RoutedEdgeSegments") -> "RoutedEdgeSegments":
        return RoutedEdgeSegments(
            segments=self.segments + other.segments,
            intersections=self.intersections + other.intersections,
        )

    def cut_with_nodes(
        self, node_buffers: Iterable[NodeBuffer]
    ) -> "RoutedEdgeSegments":
        return RoutedEdgeSegments(
            segments=[
                segment.cut_multiple(iter(node_buffers)) for segment in self.segments
            ],
            intersections=self.intersections,
        )

    @property
    def min_bound(self) -> Point:
        return Point.min_point(
            [edge_segment.min_bound for edge_segment in self.segments]
        )

    @property
    def max_bound(self) -> Point:
        return Point.max_point(
            [edge_segment.max_bound for edge_segment in self.segments]
        )

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
