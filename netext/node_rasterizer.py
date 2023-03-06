import math
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from netext.geometry import Magnet, Point
from shapely import LineString, Polygon

from netext.segment_buffer import Strip, StripBuffer, Spacer


class Shape(Protocol):
    def get_magnet_position(
        self, node_buffer: "NodeBuffer", target_point: Point, magnet: Magnet
    ) -> Point:
        return NotImplemented

    def render_shape(
        self,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> RenderableType:
        return NotImplemented


class RectangularShapeMixin:
    def get_magnet_position(
        self, node_buffer: "NodeBuffer", target_point: Point, magnet: Magnet
    ) -> Point:
        match magnet:  # noqa
            case Magnet.TOP:
                return Point(x=node_buffer.center.x, y=node_buffer.top_y)
            case Magnet.LEFT:
                return Point(x=node_buffer.left_x, y=node_buffer.center.y)
            case Magnet.BOTTOM:
                return Point(x=node_buffer.center.x, y=node_buffer.bottom_y)
            case Magnet.RIGHT:
                return Point(x=node_buffer.right_x, y=node_buffer.center.y)
            case Magnet.CENTER:
                direct_line = LineString(
                    [node_buffer.center.shapely_point(), target_point.shapely_point()]
                )
                node_polygon = Polygon(
                    [
                        (node_buffer.left_x, node_buffer.top_y),
                        (node_buffer.right_x, node_buffer.top_y),
                        (node_buffer.right_x, node_buffer.bottom_y),
                        (node_buffer.left_x, node_buffer.bottom_y),
                    ]
                )

                intersection = direct_line.intersection(node_polygon)
                intersection_point = intersection.line_interpolate_point(
                    1.0, normalized=True
                )
                return Point(
                    x=round(intersection_point.x), y=round(intersection_point.y)
                )
        raise RuntimeError(magnet)


class JustContent(RectangularShapeMixin):
    def render_shape(
        self,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> RenderableType:
        return content_renderable


class Box(RectangularShapeMixin):
    def render_shape(
        self,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> RenderableType:
        box_type = data.get("$box-type", box.ROUNDED)
        return Panel(content_renderable, expand=False, style=style, box=box_type)


@dataclass
class NodeBuffer(StripBuffer):
    center: Point
    node_width: int
    node_height: int

    shape: Shape = JustContent()

    @property
    def left_x(self) -> int:
        return self.center.x - math.ceil((self.width - 1) / 2.0)

    @property
    def right_x(self) -> int:
        return self.center.x + math.floor((self.width - 1) / 2.0)

    @property
    def top_y(self) -> int:
        return self.center.y - math.ceil((self.height - 1) / 2.0)

    @property
    def bottom_y(self) -> int:
        return self.center.y + math.floor((self.height - 1) / 2.0)

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
    shape: Shape = data.get("$shape", Box())
    style: Style = data.get("$style", Style())
    content_style = data.get("$content-style", Style())
    content_renderer = data.get("$content-renderer", _default_content_renderer)
    content_renderable = content_renderer(str(node), data, content_style)

    # TODO render shape needs to return a strip as it could have spacers
    node_renderable = shape.render_shape(content_renderable, style=style, data=data)

    segment_lists = list(console.render_lines(node_renderable, pad=False))
    strips = [
        Strip(segments=cast(list[Segment | Spacer], segments))
        for segments in segment_lists
    ]
    width = max(
        sum(segment.cell_length for segment in strip.segments) for strip in strips
    )

    node_buffer = NodeBuffer(
        shape=shape,
        center=Point(x=0, y=0),
        z_index=-1,
        node_width=width,
        node_height=len(strips),
        strips=strips,
    )
    return node_buffer
