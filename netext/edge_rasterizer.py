from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from bitarray import bitarray
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from netext.geometry import Point, Magnet

from netext.node_rasterizer import JustContent, NodeBuffer
from netext.segment_buffer import Strip, StripBuffer, Spacer


class EdgeRoutingMode(Enum):
    straight = "straight"
    orthogonal = "orthogonal"


class EdgeSegmentDrawingMode(Enum):
    box = "box"
    single_character = "single_character"
    braille = "braille"


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
    start: Point, end: Point, routing_mode: EdgeRoutingMode
) -> list[EdgeSegment]:
    match routing_mode:  # noqa: E999
        case EdgeRoutingMode.straight:
            return [EdgeSegment(start=start, end=end)]
        case EdgeRoutingMode.orthogonal:
            return [
                EdgeSegment(start=start, end=Point(x=start.x, y=end.y)),
                EdgeSegment(start=Point(x=start.x, y=end.y), end=end),
            ]
        case _:
            raise NotImplementedError(
                f"The routing mode {routing_mode} has not been implemented yet."
            )


def rasterize_edge_segments(
    edge_segments: list[EdgeSegment], scaling: int
) -> BitmapBuffer:
    min_point = Point(
        x=min([min([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=min([min([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    max_point = Point(
        x=max([max([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=max([max([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    width = (max_point.x - min_point.x + 1) * scaling
    height = (max_point.y - min_point.y + 1) * scaling
    buffer = bitarray(width * height)
    buffer.setall(0)
    bitmap_buffer = BitmapBuffer(
        x=min_point.x * scaling,
        y=min_point.y * scaling,
        width=width,
        height=height,
        buffer=buffer,
    )

    for edge_segment in edge_segments:
        scaled_segment = EdgeSegment(
            start=Point(edge_segment.start.x * scaling, edge_segment.start.y * scaling),
            end=Point(edge_segment.end.x * scaling, edge_segment.end.y * scaling),
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


def _slice_to_box_strip(slice: bitarray, width: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for x in range(0, width, 2):
        lookup = (
            (
                _infinite_canvas_access(slice, x, 0, width),
                _infinite_canvas_access(slice, x + 1, 0, width),
            ),
            (
                _infinite_canvas_access(slice, x, 1, width),
                _infinite_canvas_access(slice, x + 1, 1, width),
            ),
        )
        match lookup:
            case ((0, 0), (0, 0)):
                current_segment.append(Spacer(width=1))
            case ((0, 1), (0, 1)) | ((1, 0), (1, 0)):
                current_segment.append(Segment("│"))
            case ((1, 1), (0, 0)) | ((0, 0), (1, 1)):
                current_segment.append(Segment("─"))
            case ((1, 0), (0, 1)):
                current_segment.append(Segment("╲"))
            case ((0, 1), (1, 0)):
                current_segment.append(Segment("╱"))
            case _:
                current_segment.append(Spacer(width=1))

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
        case EdgeSegmentDrawingMode.box:
            lines = [
                _slice_to_box_strip(
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
    char_buffer = [[None] * width] * height

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

    for edge_segment, next_segment in zip(
        offset_edge_segments, offset_edge_segments[1:] + [None]
    ):
        if edge_segment.start.x == edge_segment.end.x:
            for y in range(edge_segment.start.y, edge_segment.end.y):
                char_buffer[y][edge_segment.start.x] = "│"
        else:
            for x in range(edge_segment.start.x, edge_segment.end.x):
                char_buffer[edge_segment.start.y][x] = "─"

    return [
        Strip(
            [
                Segment(text=character) if character is not None else Spacer(width=1)
                for character in line
            ]
        )
        for line in char_buffer
    ]


# TODO: Should return an edge buffer (the edge and tips), the edge layout (to be used as optional input) and a list
# of node buffers, the labels
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
    # TODO Think about this, shape and node buffer are bound
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

    edge_segments = route_edge(start, end, routing_mode)

    if edge_segment_drawing_mode == EdgeSegmentDrawingMode.box:
        assert (
            routing_mode == EdgeRoutingMode.orthogonal
        ), "Box characters are only supported on orthogonal lines"
        strips = orthogonal_segments_to_strips_with_box_characters(edge_segments)
    else:
        # In case of pixel / braille we scale and then map character per character
        x_scaling = 1  # noqa
        y_scaling = 1  # noqa

        bitmap_buffer = rasterize_edge_segments(edge_segments, scaling=1)
        strips = bitmap_to_strips(
            bitmap_buffer, edge_segment_drawing_mode=edge_segment_drawing_mode
        )

    edge_layout = EdgeLayout(input=edge_input, segments=edge_segments)

    edge_buffer = EdgeBuffer(
        z_index=0,
        boundary_1=start,
        boundary_2=end,
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
