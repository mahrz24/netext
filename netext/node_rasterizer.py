import math

from pydantic import NonNegativeInt, PositiveInt
from rich.segment import Segment
from rich.style import Style
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

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
    console = Console(width=5, height=2)
    segment_lines = list(console.render_lines(Panel(Text(str(node)))))
    offset_segments = [OffsetSegment(x_offset=0, y_offset=i, segments=segments) for i, segments in enumerate(segment_lines)]
    print(offset_segments)
    return NodeBuffer(
        x=0,
        y=0,
        z_index=-1,
        width=5,
        height=len(offset_segments),
        offset_segments=offset_segments,
    )
