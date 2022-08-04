import math

from pydantic import NonNegativeInt, PositiveInt
from rich.segment import Segment
from rich.style import Style

from .segment_buffer import OffsetSegment, SegmentBuffer


class NodeBuffer(SegmentBuffer):
    x: NonNegativeInt
    y: NonNegativeInt
    width: PositiveInt
    height: PositiveInt

    @property
    def left_x(self):
        return self.x - math.floor(self.width / 2.0)

    @property
    def right_x(self):
        return self.x + math.floor(self.width / 2.0)

    @property
    def top_y(self):
        return self.y - math.floor(self.height / 2.0)

    @property
    def bottom_y(self):
        return self.y + math.floor(self.height / 2.0)


def rasterize_node(node, data) -> NodeBuffer:
    segment = Segment(str(node), Style(color="red"))
    return NodeBuffer(
        x=0,
        y=0,
        z_index=-1,
        width=segment.cell_length,
        height=1,
        segments=[OffsetSegment(x_offset=0, y_offset=0, segment=segment)],
    )
