import math
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, cast

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.text import Text

from netext.segment_buffer import OffsetLine, SegmentBuffer, Spacer


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


def _default_content_renderer(
    node_str: str, data: dict[Hashable, Any], content_style: Style
) -> RenderableType:
    return Text(node_str, style=content_style)


def rasterize_node(
    console: Console, node: Hashable, data: dict[Hashable, Any]
) -> NodeBuffer:
    shape = data.get("$shape", "box")
    style = data.get("$style", Style())
    content_style = data.get("$content-style", Style())
    content_renderer = data.get("$node-renderer", _default_content_renderer)
    content_renderable = content_renderer(str(node), data, content_style)

    if shape == "box":
        box_type = data.get("$box-type", box.ROUNDED)
        node_renderable = Panel(
            content_renderable, expand=False, style=style, box=box_type
        )
    else:
        node_renderable = content_renderable

    segment_lines = list(console.render_lines(node_renderable, pad=False))
    segment_lines = [
        OffsetLine(
            x_offset=0, y_offset=i, segments=cast(list[Segment | Spacer], segments)
        )
        for i, segments in enumerate(segment_lines)
    ]
    width = max(
        segment_line.x_offset
        + sum(segment.cell_length for segment in segment_line.segments)
        for segment_line in segment_lines
    )

    node_buffer = NodeBuffer(
        x=0,
        y=0,
        z_index=-1,
        node_width=width,
        node_height=len(segment_lines),
        segment_lines=segment_lines,
    )
    return node_buffer
