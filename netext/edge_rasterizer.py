from typing import Any, Dict, Hashable, List

import grandalf.graphs
from pydantic import BaseModel, NonNegativeInt
from rich.segment import Segment
from rich.style import Style

from .node_rasterizer import NodeBuffer
from .segment_buffer import OffsetSegment, SegmentBuffer


# TODO: Use also in node buffer
class Point(BaseModel):
    x: NonNegativeInt
    y: NonNegativeInt


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


def rasterize_edge(
    u_buffer: NodeBuffer, v_buffer: NodeBuffer, data: Dict[Hashable, Any]
) -> EdgeBuffer:
    # TODO: In the first prototype we just support straight lines from
    # center point to center point
    x0 = u_buffer.x
    y0 = u_buffer.y

    x1 = v_buffer.x
    y1 = v_buffer.y

    segments = []

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
                segments.append(
                    OffsetSegment(
                        x_offset=last_offset,
                        y_offset=0,
                        segment=Segment(current_segment, Style(color="green")),
                    )
                )
                current_segment = ""
                last_offset = x-x0
                D = D - 2 * dx
            D = D + 2 * dy

        segments.append(
            OffsetSegment(
                x_offset=last_offset,
                y_offset=0,
                segment=Segment(current_segment, Style(color="green")),
            )
        )

        if reverse:
            segments = list(reversed(segments))
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

        for y in range(y0, y1+1):
            segments.append(
                OffsetSegment(
                    x_offset=x,
                    y_offset=0,
                    segment=Segment(".", Style(color="green")),
                )
            )
            if D > 0:
                x = x + xi
                D = D + (2 * (dx - dy))
            else:
                D = D + 2*dx

    for i, segment in enumerate(segments):
        segment.y_offset = i

    edge_buffer = EdgeBuffer(
        start=Point(x=x0, y=y0), end=Point(x=x1, y=y1), segments=segments
    )

    return edge_buffer
