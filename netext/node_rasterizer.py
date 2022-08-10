import math
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from .segment_buffer import OffsetLine, SegmentBuffer


@dataclass
class NodeBuffer(SegmentBuffer):
    x: int
    y: int
    node_width: int
    node_height: int

    @property
    def left_x(self):
        return self.x - math.ceil((self.width - 1) / 2.0)

    @property
    def right_x(self):
        return self.x + math.floor((self.width - 1) / 2.0)

    @property
    def top_y(self):
        return self.y - math.ceil((self.height - 1) / 2.0)

    @property
    def bottom_y(self):
        return self.y + math.floor((self.height - 1) / 2.0)

    @property
    def width(self):
        return self.node_width

    @property
    def height(self):
        return self.node_height


def rasterize_node(node, data) -> NodeBuffer:
    # TODO pass console
    console = Console()

    # Allow custom renderable, specific shapes (for non square rendering)
    table = Table(title="Node")

    table.add_column("Node", justify="right", style="cyan", no_wrap=True)
    table.add_column("Data", style="magenta")

    table.add_row(str(node), repr(data))

    segment_lines = list(console.render_lines(table, pad=False))
    segment_lines = [
        OffsetLine(x_offset=0, y_offset=i, segments=segments)
        for i, segments in enumerate(segment_lines)
    ]
    width = sum(segment.cell_length for segment in segment_lines[0].segments)
    return NodeBuffer(
        x=0,
        y=0,
        z_index=-1,
        node_width=width,
        node_height=len(segment_lines),
        segment_lines=segment_lines,
    )
