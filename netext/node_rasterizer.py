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

from netext.rendering.segment_buffer import Strip, StripBuffer, Spacer


class Shape(Protocol):
    def get_magnet_position(
        self, node_buffer: "NodeBuffer", target_point: Point, magnet: Magnet
    ) -> Point:
        return NotImplemented

    def polygon(self, node_buffer: "NodeBuffer", margin: float = 0) -> Polygon:
        return NotImplemented

    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> list[Strip]:
        return NotImplemented


class RectangularShapeMixin:
    def _renderable_type_to_strips(
        self, console: Console, node_renderable: RenderableType
    ) -> list[Strip]:
        segment_lists = list(console.render_lines(node_renderable, pad=False))
        return [
            Strip(segments=cast(list[Segment | Spacer], segments))
            for segments in segment_lists
        ]

    def polygon(self, node_buffer: "NodeBuffer", margin: float = 0) -> Polygon:
        return Polygon(
            [
                (node_buffer.left_x - margin, node_buffer.top_y - margin),
                (node_buffer.right_x + margin, node_buffer.top_y - margin),
                (node_buffer.right_x + margin, node_buffer.bottom_y + margin),
                (node_buffer.left_x - margin, node_buffer.bottom_y + margin),
            ]
        )

    def get_magnet_position(
        self, node_buffer: "NodeBuffer", target_point: Point, magnet: Magnet
    ) -> Point:
        match magnet:
            case Magnet.TOP:
                return Point(x=node_buffer.center.x, y=node_buffer.top_y)
            case Magnet.LEFT:
                return Point(x=node_buffer.left_x, y=node_buffer.center.y)
            case Magnet.BOTTOM:
                return Point(x=node_buffer.center.x, y=node_buffer.bottom_y)
            case Magnet.RIGHT:
                return Point(x=node_buffer.right_x, y=node_buffer.center.y)
            case Magnet.CENTER:
                return node_buffer.center
            case Magnet.CLOSEST:
                direct_line = LineString(
                    [node_buffer.center.shapely, target_point.shapely]
                )
                node_polygon = self.polygon(node_buffer)
                intersection = direct_line.intersection(node_polygon)
                intersection_point = intersection.line_interpolate_point(
                    1.0, normalized=True
                )
                if intersection_point.is_empty:
                    return node_buffer.center

                closest_magnet = Magnet.TOP
                closest_point = self.get_magnet_position(
                    node_buffer=node_buffer,
                    target_point=target_point,
                    magnet=closest_magnet,
                )
                closest_distance = intersection_point.distance(closest_point.shapely)

                for magnet in [Magnet.LEFT, Magnet.RIGHT, Magnet.BOTTOM]:
                    point = self.get_magnet_position(
                        node_buffer=node_buffer,
                        target_point=target_point,
                        magnet=magnet,
                    )
                    distance = intersection_point.distance(point.shapely)
                    if distance < closest_distance:
                        closest_point = point
                        closest_distance = distance

                return closest_point
        raise RuntimeError(magnet)


class JustContent(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> list[Strip]:
        return self._renderable_type_to_strips(console, content_renderable)


class Box(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        data: dict[Hashable, Any],
    ) -> list[Strip]:
        box_type = data.get("$box-type", box.ROUNDED)
        return self._renderable_type_to_strips(
            console, Panel(content_renderable, expand=False, style=style, box=box_type)
        )


@dataclass
class NodeBuffer(StripBuffer):
    center: Point
    node_width: int
    node_height: int

    shape: Shape = JustContent()

    @classmethod
    def from_strips(
        cls,
        strips: list[Strip],
        center: Point,
        shape: Shape,
        z_index: int = 0,
    ) -> "NodeBuffer":
        width = max(
            sum(segment.cell_length for segment in strip.segments) for strip in strips
        )

        return cls(
            shape=shape,
            center=center,
            z_index=-1,
            node_width=width,
            node_height=len(strips),
            strips=strips,
        )

    def get_magnet_position(self, target_point: Point, magnet: Magnet) -> Point:
        return self.shape.get_magnet_position(
            self, target_point=target_point, magnet=magnet
        )

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
    strips = shape.render_shape(console, content_renderable, style=style, data=data)

    return NodeBuffer.from_strips(
        strips, center=Point(x=0, y=0), z_index=-1, shape=shape
    )
