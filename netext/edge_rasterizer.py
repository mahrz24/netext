from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from bitarray import bitarray
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from netext.geometry import Point, Magnet
from shapely import LineString

from netext.node_rasterizer import JustContent, NodeBuffer
from netext.segment_buffer import Strip, StripBuffer, Spacer


class EdgeRoutingMode(Enum):
    straight = "straight"
    orthogonal = "orthogonal"


class EdgeSegmentDrawingMode(Enum):
    box = "box"
    single_character = "single_character"
    braille = "braille"
    block = "block"


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
class EdgeSegment:
    start: Point
    end: Point

    def length(self) -> float:
        return self.start.distance_to(self.end)

    def intersects_with_node(self, node_buffer: NodeBuffer) -> bool:
        direct_line = LineString([self.start.shapely_point(), self.end.shapely_point()])
        node_polygon = node_buffer.shape.bounding_box(node_buffer)
        intersection = direct_line.intersection(node_polygon)
        return not intersection.is_empty

    def cut(self, node_buffer: NodeBuffer) -> "EdgeSegment":
        start = self.start.shapely_point()
        end = self.end.shapely_point()
        direct_line = LineString([start, end])
        node_polygon = node_buffer.shape.bounding_box(node_buffer)
        node_polygon_boundary = node_polygon.boundary
        intersection = direct_line.intersection(node_polygon_boundary)
        if isinstance(intersection, LineString):
            intersection = intersection.interpolate(1)
        intersection_start = start.intersection(node_polygon)
        if intersection.is_empty:
            return self
        else:
            if intersection_start.is_empty:
                return EdgeSegment(
                    start=self.start,
                    end=Point.from_shapely_point(intersection),
                )
            else:
                return EdgeSegment(
                    start=Point.from_shapely_point(intersection),
                    end=self.end,
                )

    def count_node_intersections(self, node_buffers: Iterable[NodeBuffer]) -> int:
        return sum(
            1 for node_buffer in node_buffers if self.intersects_with_node(node_buffer)
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

    @property
    def midpoint(self) -> Point:
        return (self.start + self.end) / 2

    @property
    def start_y_mid(self) -> Point:
        return Point(x=self.midpoint.x, y=self.start.y)

    @property
    def end_y_mid(self) -> Point:
        return Point(x=self.midpoint.x, y=self.end.y)

    @property
    def start_x_mid(self) -> Point:
        return Point(x=self.start.x, y=self.midpoint.y)

    @property
    def end_x_mid(self) -> Point:
        return Point(x=self.end.x, y=self.midpoint.y)

    @property
    def min_bound(self) -> Point:
        return Point(x=min(self.start.x, self.end.x), y=min(self.start.y, self.end.y))

    @property
    def max_bound(self) -> Point:
        return Point(x=max(self.start.x, self.end.x), y=max(self.start.y, self.end.y))


@dataclass
class RoutedEdgeSegments:
    segments: list[EdgeSegment]
    intersections: int

    @classmethod
    def from_segments(
        cls, segments: list[EdgeSegment], node_buffers: Iterable[NodeBuffer]
    ) -> "RoutedEdgeSegments":
        return cls(
            segments=segments,
            intersections=sum(
                segment.count_node_intersections(node_buffers) for segment in segments
            ),
        )

    def concat(self, other: "RoutedEdgeSegments") -> "RoutedEdgeSegments":
        return RoutedEdgeSegments(
            segments=self.segments + other.segments,
            intersections=self.intersections + other.intersections,
        )


@dataclass
class EdgeLayout:
    input: EdgeInput
    segments: list[EdgeSegment]

    # label_position: Point | None
    # start_tip_position: Point | None
    # end_tip_position: Point | None


@dataclass
class BitmapBuffer:
    x: int
    y: int
    width: int
    height: int
    buffer: bitarray

    def __rich__(self) -> str:
        markup_str = "[bold green]"
        for i in range(self.height):
            markup_str += (
                self.buffer[i * self.width : (i + 1) * self.width]
                .unpack(zero=b".", one=b"X")
                .decode("utf-8")
                + "\n"
            )
        markup_str += f"[/bold green]at (x={self.x}, y={self.y})"
        return markup_str


@dataclass
class EdgeBuffer(StripBuffer):
    boundary_1: Point
    boundary_2: Point

    @property
    def left_x(self) -> int:
        return min(self.boundary_1.x, self.boundary_2.x)

    @property
    def right_x(self) -> int:
        return max(self.boundary_1.x, self.boundary_2.x)

    @property
    def top_y(self) -> int:
        return min(self.boundary_1.y, self.boundary_2.y)

    @property
    def bottom_y(self) -> int:
        return max(self.boundary_1.y, self.boundary_2.y)

    @property
    def width(self) -> int:
        return self.right_x - self.left_x + 1

    @property
    def height(self) -> int:
        return self.bottom_y - self.top_y + 1


def route_edge(
    start: Point,
    end: Point,
    routing_mode: EdgeRoutingMode,
    non_start_end_nodes: Iterable[NodeBuffer] = [],
    routed_edges: Iterable[EdgeLayout] = [],
) -> list[EdgeSegment]:
    match routing_mode:
        case EdgeRoutingMode.straight:
            return [EdgeSegment(start=start, end=end)]
        case EdgeRoutingMode.orthogonal:
            return route_orthogonal_edge(
                start=start,
                end=end,
                non_start_end_nodes=non_start_end_nodes,
            ).segments
        case _:
            raise NotImplementedError(
                f"The routing mode {routing_mode} has not been implemented yet."
            )


def route_orthogonal_edge(
    start: Point,
    end: Point,
    non_start_end_nodes: Iterable[NodeBuffer],
) -> RoutedEdgeSegments:
    """
    Route an edge from start to end using orthogonal segments.

    The edge will be routed in a way that minimizes the number of intersections with other nodes.

    """
    # TODO: Also check intersections with other edges.
    # TODO: Add different midpoints as candidates.
    candidates = [
        RoutedEdgeSegments.from_segments(
            EdgeSegment(start=start, end=end).ortho_split_x(),
            node_buffers=non_start_end_nodes,
        ),
        RoutedEdgeSegments.from_segments(
            EdgeSegment(start=start, end=end).ortho_split_y(),
            node_buffers=non_start_end_nodes,
        ),
    ]

    if (
        all([candidate.intersections > 0 for candidate in candidates])
        and start.distance_to(end) >= 2
    ):
        candidates.append(
            route_orthogonal_edge(
                start=start,
                end=EdgeSegment(start=start, end=end).midpoint,
                non_start_end_nodes=non_start_end_nodes,
            ).concat(
                route_orthogonal_edge(
                    start=EdgeSegment(start=start, end=end).midpoint,
                    end=end,
                    non_start_end_nodes=non_start_end_nodes,
                )
            )
        )

    return min(candidates, key=lambda candidate: candidate.intersections)


def rasterize_edge_segments(
    edge_segments: list[EdgeSegment], x_scaling: int, y_scaling: int
) -> BitmapBuffer:
    min_point = Point(
        x=min([min([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=min([min([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    max_point = Point(
        x=max([max([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=max([max([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    width = (max_point.x - min_point.x + 1) * x_scaling
    height = (max_point.y - min_point.y + 1) * y_scaling
    buffer = bitarray(width * height)
    buffer.setall(0)
    bitmap_buffer = BitmapBuffer(
        x=min_point.x * x_scaling,
        y=min_point.y * y_scaling,
        width=width,
        height=height,
        buffer=buffer,
    )

    for edge_segment in edge_segments:
        scaled_segment = EdgeSegment(
            start=Point(
                edge_segment.start.x * x_scaling, edge_segment.start.y * y_scaling
            ),
            end=Point(edge_segment.end.x * x_scaling, edge_segment.end.y * y_scaling),
        )
        _bresenham_line_drawing(scaled_segment, bitmap_buffer=bitmap_buffer)

    return bitmap_buffer


def _slice_to_strip(slice: bitarray) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for val in slice:
        if not val:
            current_segment.append(Spacer(width=1))
        else:
            current_segment.append(Segment("*"))

    return Strip(segments=current_segment)


def _infinite_canvas_access(slice: bitarray, x: int, y: int, width: int) -> int:
    index = width * y + x
    if index < 0:
        return 0
    elif index >= len(slice):
        return 0
    else:
        return slice[index]


def _slice_to_braille_strip(slice: bitarray, width: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for x in range(0, width, 2):
        lookup = (
            _infinite_canvas_access(slice, x, 0, width),
            _infinite_canvas_access(slice, x, 1, width),
            _infinite_canvas_access(slice, x, 2, width),
            _infinite_canvas_access(slice, x + 1, 0, width),
            _infinite_canvas_access(slice, x + 1, 1, width),
            _infinite_canvas_access(slice, x + 1, 2, width),
            _infinite_canvas_access(slice, x, 3, width),
            _infinite_canvas_access(slice, x + 1, 3, width),
        )
        if all([val == 0 for val in lookup]):
            current_segment.append(Spacer(width=1))
            continue
        current_segment.append(
            Segment(chr(0x2800 + sum([2**i for i, val in enumerate(lookup) if val])))
        )

    return Strip(segments=current_segment)


def _slice_to_block_strip(slice: bitarray, width: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for x in range(0, width, 2):
        lookup = (
            _infinite_canvas_access(slice, x, 0, width),
            _infinite_canvas_access(slice, x + 1, 0, width),
            _infinite_canvas_access(slice, x, 1, width),
            _infinite_canvas_access(slice, x + 1, 1, width),
        )
        if all([val == 0 for val in lookup]):
            current_segment.append(Spacer(width=1))
            continue

        block = sum([2**i for i, val in enumerate(lookup) if val])
        match block:
            case 1:
                current_segment.append(Segment("▘"))
            case 2:
                current_segment.append(Segment("▝"))
            case 3:
                current_segment.append(Segment("▀"))
            case 4:
                current_segment.append(Segment("▖"))
            case 5:
                current_segment.append(Segment("▌"))
            case 6:
                current_segment.append(Segment("▞"))
            case 7:
                current_segment.append(Segment("▛"))
            case 8:
                current_segment.append(Segment("▗"))
            case 9:
                current_segment.append(Segment("▚"))
            case 10:
                current_segment.append(Segment("▐"))
            case 11:
                current_segment.append(Segment("▜"))
            case 12:
                current_segment.append(Segment("▄"))
            case 13:
                current_segment.append(Segment("▙"))
            case 14:
                current_segment.append(Segment("▟"))
            case 15:
                current_segment.append(Segment("█"))

    return Strip(segments=current_segment)


def bitmap_to_strips(
    bitmap_buffer: BitmapBuffer, edge_segment_drawing_mode: EdgeSegmentDrawingMode
) -> list[Strip]:
    match edge_segment_drawing_mode:
        case EdgeSegmentDrawingMode.single_character:
            lines = [
                _slice_to_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 1) * bitmap_buffer.width
                    ]
                )
                for y in range(bitmap_buffer.height)
            ]
        case EdgeSegmentDrawingMode.braille:
            lines = [
                _slice_to_braille_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 4) * bitmap_buffer.width
                    ],
                    bitmap_buffer.width,
                )
                for y in range(0, bitmap_buffer.height, 4)
            ]
        case EdgeSegmentDrawingMode.block:
            lines = [
                _slice_to_block_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 2) * bitmap_buffer.width
                    ],
                    bitmap_buffer.width,
                )
                for y in range(0, bitmap_buffer.height, 2)
            ]
        case _:
            raise NotImplementedError(
                "The edge segement drawing mode has not yet been implemented"
            )

    return lines


def orthogonal_segments_to_strips_with_box_characters(
    edge_segments: list[EdgeSegment],
) -> list[Strip]:
    if not edge_segments:
        return []

    min_point = Point(
        x=min([min([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=min([min([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    max_point = Point(
        x=max([max([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=max([max([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    width = max_point.x - min_point.x + 1
    height = max_point.y - min_point.y + 1
    char_buffer: list[list[str | None]] = list()
    for y in range(height):
        char_buffer.append(list([None] * width))
    offset_edge_segments = [
        EdgeSegment(
            start=Point(
                edge_segment.start.x - min_point.x, edge_segment.start.y - min_point.y
            ),
            end=Point(
                edge_segment.end.x - min_point.x, edge_segment.end.y - min_point.y
            ),
        )
        for edge_segment in edge_segments
    ]
    last_segment: EdgeSegment | None = None
    for edge_segment in offset_edge_segments:
        start, end = edge_segment.start, edge_segment.end
        if start.x == end.x:
            for y in range(
                min(start.y, end.y),
                max(start.y, end.y) + 1,
            ):
                if char_buffer[y][start.x] == "─" and last_segment is not None:
                    if last_segment.end.y < end.y:
                        if last_segment.start.x < start.x:
                            char_buffer[y][start.x] = "╮"
                        else:
                            char_buffer[y][start.x] = "╭"
                    else:
                        if last_segment.start.x < start.x:
                            char_buffer[y][start.x] = "╯"
                        else:
                            char_buffer[y][start.x] = "╰"
                else:
                    char_buffer[y][start.x] = "│"
        elif start.y == end.y:
            for x in range(
                min(start.x, end.x),
                max(start.x, end.x) + 1,
            ):
                if char_buffer[start.y][x] == "│" and last_segment is not None:
                    if last_segment.end.y < end.y:
                        if last_segment.start.x < start.x:
                            char_buffer[start.y][x] = "╮"
                        else:
                            char_buffer[start.y][x] = "╭"
                    else:
                        if last_segment.start.x < start.x:
                            char_buffer[start.y][x] = "╯"
                        else:
                            char_buffer[start.y][x] = "╰"
                else:
                    char_buffer[start.y][x] = "─"

        last_segment = edge_segment

    return [
        Strip(
            [
                Segment(text=character) if character is not None else Spacer(width=1)
                for character in line
            ]
        )
        for line in char_buffer
    ]


def cut_edge_segments_with_start_and_end_nodes(
    edge_segments: list[EdgeSegment],
    start_node: NodeBuffer,
    end_node: NodeBuffer,
) -> list[EdgeSegment]:
    return [segment.cut(start_node).cut(end_node) for segment in edge_segments]


def rasterize_edge(
    console: Console,
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    all_nodes: Iterable[NodeBuffer],
    routed_edges: Iterable[EdgeLayout],
    data: Any,
) -> tuple[EdgeBuffer, EdgeLayout, list[NodeBuffer]]:
    start = u_buffer.get_magnet_position(
        v_buffer.center, data.get("$magnet", Magnet.CENTER)
    )

    end = v_buffer.get_magnet_position(
        u_buffer.center, data.get("$magnet", Magnet.CENTER)
    )

    routing_mode: EdgeRoutingMode = data.get(
        "$edge-routing-mode", EdgeRoutingMode.straight
    )
    edge_segment_drawing_mode: EdgeSegmentDrawingMode = data.get(
        "$edge-segment-drawing-mode", EdgeSegmentDrawingMode.single_character
    )

    edge_input = EdgeInput(
        start=start,
        end=end,
        routing_mode=routing_mode,
        edge_segment_drawing_mode=edge_segment_drawing_mode,
        routing_hints=[],
    )

    label_buffers = []
    label = data.get("$label", None)

    # TODO Think about this: Shape and node buffer are bound
    # so maybe use the shape to create the node buffer
    # and link it to the creating shape?
    if label is not None:
        shape = JustContent()
        label_strips = shape.render_shape(console, label, style=Style(), data={})
        label_buffer = NodeBuffer.from_strips(
            label_strips,
            z_index=1,
            shape=shape,
            center=Point(
                x=round((start.x + end.x) / 2), y=round((start.y + end.y) / 2)
            ),
        )
        label_buffers.append(label_buffer)

    # We perform a two pass routing here.

    # First we route the edge with allowing the center magnet as start and end
    # This routing already tries to avoid other nodes.
    non_start_end_nodes = [
        node_buffer
        for node_buffer in all_nodes
        if node_buffer is not u_buffer and node_buffer is not v_buffer
    ]

    edge_segments = route_edge(
        start, end, routing_mode, non_start_end_nodes, routed_edges
    )

    # Then we cut the edge with the node boundaries.
    edge_segments = cut_edge_segments_with_start_and_end_nodes(
        edge_segments, u_buffer, v_buffer
    )

    if edge_segment_drawing_mode == EdgeSegmentDrawingMode.box:
        assert (
            routing_mode == EdgeRoutingMode.orthogonal
        ), "Box characters are only supported on orthogonal lines"
        strips = orthogonal_segments_to_strips_with_box_characters(edge_segments)
    else:
        # In case of pixel / braille we scale and then map character per character
        match edge_segment_drawing_mode:
            case EdgeSegmentDrawingMode.single_character:
                x_scaling = 1
                y_scaling = 1
            case EdgeSegmentDrawingMode.braille:
                x_scaling = 2
                y_scaling = 4
            case EdgeSegmentDrawingMode.block:
                x_scaling = 2
                y_scaling = 2

        bitmap_buffer = rasterize_edge_segments(
            edge_segments, x_scaling=x_scaling, y_scaling=y_scaling
        )
        strips = bitmap_to_strips(
            bitmap_buffer, edge_segment_drawing_mode=edge_segment_drawing_mode
        )

    edge_layout = EdgeLayout(input=edge_input, segments=edge_segments)

    boundary_1 = Point.min_point(
        [edge_segment.min_bound for edge_segment in edge_segments]
    )
    boundary_2 = Point.max_point(
        [edge_segment.max_bound for edge_segment in edge_segments]
    )

    edge_buffer = EdgeBuffer(
        z_index=0,
        boundary_1=boundary_1,
        boundary_2=boundary_2,
        strips=strips,
    )

    return edge_buffer, edge_layout, label_buffers


def _bresenham_line_drawing(
    edge_segment: EdgeSegment, bitmap_buffer: BitmapBuffer
) -> None:
    x0 = edge_segment.start.x - bitmap_buffer.x
    x1 = edge_segment.end.x - bitmap_buffer.x

    y0 = edge_segment.start.y - bitmap_buffer.y
    y1 = edge_segment.end.y - bitmap_buffer.y

    if abs(y1 - y0) < abs(x1 - x0):
        if x0 > x1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1
        _bresenham_flat(x0, y0, x1, y1, bitmap_buffer)
    else:
        if y0 > y1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1
        _bresenham_steep(x0, y0, x1, y1, bitmap_buffer)


def _bresenham_flat(
    x0: int, y0: int, x1: int, y1: int, bitmap_buffer: BitmapBuffer
) -> None:
    dx = x1 - x0
    dy = y1 - y0
    yi = 1

    if dy < 0:
        yi = -1
        dy = -dy

    y = y0
    D = 2 * dy - dx

    for x in range(x0, x1 + 1):
        _put_pixel(x, y, bitmap_buffer)
        if D > 0:
            y += yi
            D = D + (2 * (dy - dx))
        else:
            D = D + 2 * dy


def _put_pixel(x: int, y: int, bitmap_buffer: BitmapBuffer) -> None:
    bitmap_buffer.buffer[x + y * bitmap_buffer.width] = True


def _bresenham_steep(
    x0: int, y0: int, x1: int, y1: int, bitmap_buffer: BitmapBuffer
) -> None:
    dx = x1 - x0
    dy = y1 - y0
    xi = 1
    if dx < 0:
        x = x0 - x1
        xi = -1
        dx = -dx
    D = (2 * dx) - dy
    x = x0

    for y in range(y0, y1 + 1):
        _put_pixel(x, y, bitmap_buffer)
        if D > 0:
            x = x + xi
            D = D + (2 * (dx - dy))
        else:
            D = D + 2 * dx
