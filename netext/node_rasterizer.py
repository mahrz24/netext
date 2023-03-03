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

from netext.segment_buffer import Strip, StripBuffer, Spacer


@dataclass
class NodeBuffer(StripBuffer):
    x: int
    y: int
    node_width: int
    node_height: int

    @property
    def left_x(self) -> int:
        return self.x - math.ceil((self.width - 1) / 2.0)

    @property
    def right_x(self) -> int:
        return self.x + math.floor((self.width - 1) / 2.0)

    @property
    def top_y(self) -> int:
        return self.y - math.ceil((self.height - 1) / 2.0)

    @property
    def bottom_y(self) -> int:
        return self.y + math.floor((self.height - 1) / 2.0)

    @property
    def width(self) -> int:
        return self.node_width

    @property
    def height(self) -> int:
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
    content_renderer = data.get("$content-renderer", _default_content_renderer)
    content_renderable = content_renderer(str(node), data, content_style)

    if shape == "box":
        box_type = data.get("$box-type", box.ROUNDED)
        node_renderable = Panel(
            content_renderable, expand=False, style=style, box=box_type
        )
    else:
        node_renderable = content_renderable

    segment_lists = list(console.render_lines(node_renderable, pad=False))
    strips = [
        Strip(segments=cast(list[Segment | Spacer], segments))
        for segments in segment_lists
    ]
    width = max(
        sum(segment.cell_length for segment in strip.segments) for strip in strips
    )

    node_buffer = NodeBuffer(
        x=0,
        y=0,
        z_index=-1,
        node_width=width,
        node_height=len(strips),
        strips=strips,
    )
    return node_buffer
