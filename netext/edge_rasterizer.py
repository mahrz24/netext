from dataclasses import dataclass
from enum import Enum
from typing import Any

from bitarray import bitarray
from rich.console import Console
from rich.segment import Segment

from netext.node_rasterizer import NodeBuffer
from netext.segment_buffer import Strip, SegmentBuffer, Spacer


class EdgeRoutingMode(Enum):
    straight = "straight"
    orthogonal = "orthogonal"


class MagnetPosition(Enum):
    center = "center"


class EdgeSegmentDrawingMode(Enum):
    box = "box"
    single_character = "single_character"
    braille = "braille"


# TODO: Use also in node buffer
@dataclass
class Point:
    x: int
    y: int


@dataclass
class Edge:
    start: Point
    end: Point
    label: str | None
    routing_mode: EdgeRoutingMode
    edge_segment_drawing_mode: EdgeSegmentDrawingMode


@dataclass
class EdgeSegment:
    start: Point
    end: Point


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
class EdgeBuffer(SegmentBuffer):
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


def get_magnet(buffer: NodeBuffer, magnet: MagnetPosition) -> Point:
    return Point(buffer.x, buffer.y)


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
    edge_segments: list[EdgeSegment], sampling: int
) -> BitmapBuffer:
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
    buffer = bitarray(width * height)
    buffer.setall(0)
    bitmap_buffer = BitmapBuffer(
        x=min_point.x, y=min_point.y, width=width, height=height, buffer=buffer
    )

    for edge_segment in edge_segments:
        _bresenham_line_drawing(edge_segment, bitmap_buffer=bitmap_buffer)

    return bitmap_buffer


def _slice_to_strip(slice: bitarray, y_offset: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for val in slice:
        if not val:
            current_segment.append(Spacer(width=1))
        else:
            current_segment.append(Segment("*"))

    return Strip(y_offset=y_offset, segments=current_segment)


def bitmap_to_strips(
    bitmap_buffer: BitmapBuffer, edge_segment_drawing_mode: EdgeSegmentDrawingMode
) -> list[Strip]:
    match edge_segment_drawing_mode:
        case EdgeSegmentDrawingMode.single_character:
            lines = [
                _slice_to_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 1) * bitmap_buffer.width
                    ],
                    y,
                )
                for y in range(bitmap_buffer.height)
            ]
        case _:
            raise NotImplementedError(
                "The edge segement drawing mode has not yet been implemented"
            )

    return lines


def rasterize_edge(
    console: Console, u_buffer: NodeBuffer, v_buffer: NodeBuffer, data: Any
) -> EdgeBuffer:
    # TODO: In the first prototype we just support straight lines from
    # center point to center point
    start = get_magnet(u_buffer, data.get("$magnet", MagnetPosition.center))
    end = get_magnet(v_buffer, data.get("$magnet", MagnetPosition.center))
    # label = data.get("$label", None)

    routing_mode: EdgeRoutingMode = data.get(
        "$edge-routing-mode", EdgeRoutingMode.straight
    )
    edge_segment_drawing_mode: EdgeSegmentDrawingMode = data.get(
        "$edge-segment-drawing-mode", EdgeSegmentDrawingMode.single_character
    )

    edge_segments = route_edge(start, end, routing_mode)
    bitmap_buffer = rasterize_edge_segments(edge_segments, sampling=1)
    strips = bitmap_to_strips(
        bitmap_buffer, edge_segment_drawing_mode=edge_segment_drawing_mode
    )

    edge_buffer = EdgeBuffer(
        z_index=0,
        boundary_1=start,
        boundary_2=end,
        strips=strips,
    )

    return edge_buffer


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
