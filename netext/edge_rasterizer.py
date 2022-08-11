from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.segment import Segment
from rich.style import Style

from .node_rasterizer import NodeBuffer
from .segment_buffer import OffsetLine, SegmentBuffer


# TODO: Use also in node buffer
@dataclass
class Point:
    x: int
    y: int


@dataclass
class EdgeBuffer(SegmentBuffer):
    start: Point
    end: Point

    @property
    def left_x(self):
        return min(self.start.x, self.end.x)

    @property
    def right_x(self):
        return max(self.start.x, self.end.x)

    @property
    def top_y(self):
        return min(self.start.y, self.end.y)

    @property
    def bottom_y(self):
        return max(self.start.y, self.end.y)

    @property
    def width(self):
        return self.right_x - self.left_x + 1

    @property
    def height(self):
        return self.bottom_y - self.top_y + 1


def rasterize_edge(
    console: Console, u_buffer: NodeBuffer, v_buffer: NodeBuffer, data: Any
) -> EdgeBuffer:
    # TODO: In the first prototype we just support straight lines from
    # center point to center point
    x0 = u_buffer.x
    y0 = u_buffer.y

    x1 = v_buffer.x
    y1 = v_buffer.y

    offset_segments = []

    if abs(y1 - y0) < abs(x1 - x0):
        if x0 > x1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1

        dx = x1 - x0
        dy = y1 - y0

        reverse = False

        if dy < 0:
            reverse = True
            dy = -dy

        D = 2 * dy - dx
        y = y0

        last_offset = 0
        current_segment = ""

        for x in range(x0, x1 + 1):
            current_segment += "."
            if D > 0:
                offset_segments.append(
                    OffsetLine(
                        x_offset=last_offset,
                        y_offset=0,
                        segments=[Segment(current_segment, Style(color="green"))],
                    )
                )
                current_segment = ""
                last_offset = x - x0
                D = D - 2 * dx
            D = D + 2 * dy

        if current_segment:
            offset_segments.append(
                OffsetLine(
                    x_offset=last_offset,
                    y_offset=0,
                    segments=[Segment(current_segment, Style(color="green"))],
                )
            )

        if reverse:
            offset_segments = list(reversed(offset_segments))
    else:
        if y0 > y1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1

        dx = x1 - x0
        dy = y1 - y0
        xi = 1
        x = 0
        if dx < 0:
            x = x0 - x1
            xi = -1
            dx = -dx
        D = (2 * dx) - dy

        for y in range(y0, y1 + 1):
            offset_segments.append(
                OffsetLine(
                    x_offset=x,
                    y_offset=0,
                    segments=[Segment(".", Style(color="green"))],
                )
            )
            if D > 0:
                x = x + xi
                D = D + (2 * (dx - dy))
            else:
                D = D + 2 * dx

    for i, offset_segment in enumerate(offset_segments):
        offset_segment.y_offset = i

    edge_buffer = EdgeBuffer(
        z_index=0,
        start=Point(x=x0, y=y0),
        end=Point(x=x1, y=y1),
        segment_lines=offset_segments,
    )

    return edge_buffer
