from typing import List

from pydantic import BaseModel, NonNegativeInt, PositiveInt
from rich.segment import Segment
from rich.style import Style
from typing import Any

from .segment_buffer import SegmentBuffer, OffsetSegment


import math


class NodeBuffer(SegmentBuffer):
    x: NonNegativeInt
    y: NonNegativeInt
    width: PositiveInt
    height: PositiveInt

    @property
    def left_x(self):
        return self.x - math.floor(self.width / 2)

    @property
    def right_x(self):
        return self.x + math.floor(self.width / 2)

    @property
    def top_y(self):
        return self.y - math.floor(self.height / 2)

    @property
    def bottom_y(self):
        return self.y + math.floor(self.height / 2)


def rasterize_node(node, data) -> NodeBuffer:
    segment = Segment(str(node), Style(color="red"))
    return NodeBuffer(
        x=0,
        y=0,
        width=segment.cell_length,
        height=1,
        segments=[OffsetSegment(x_offset=0, y_offset=0, segment=segment)],
    )
