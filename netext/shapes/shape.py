from typing import Protocol, cast

from rich.console import Console, RenderableType
from rich.padding import PaddingDimensions
from rich.segment import Segment
from rich.style import Style

from netext._core import Direction
from netext.geometry import Magnet, Point
from shapely import LineString, Polygon
from netext.geometry.magnet import ShapeSide
from netext.properties.shape import ShapeProperties

from netext.rendering.segment_buffer import Strip, Spacer
import math
from dataclasses import dataclass
from netext.rendering.segment_buffer import StripBuffer


class Shape(Protocol):
    def get_side_position(
        self,
        shape_buffer: "ShapeBuffer",
        side: ShapeSide,
        offset: int = 0,
        extrude: int = 0
    ) -> tuple[Point, Direction]:
        return NotImplemented

    def get_closest_side(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
    ) -> ShapeSide:
        return NotImplemented

    def polygon(self, shape_buffer: "ShapeBuffer", margin: float = 0) -> Polygon:
        return NotImplemented

    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        properties: ShapeProperties,
        port_side_assignments: dict[ShapeSide, list[str]] = dict(),
    ) -> list[Strip]:
        return NotImplemented


class RectangularShapeMixin:
    def _renderable_type_to_strips(self, console: Console, node_renderable: RenderableType) -> list[Strip]:
        segment_lists = list(console.render_lines(node_renderable, pad=False))
        return [Strip(segments=cast(list[Segment | Spacer], segments)) for segments in segment_lists]

    def polygon(self, shape_buffer: "ShapeBuffer", margin: float = 0) -> Polygon:
        return Polygon(
            [
                (shape_buffer.left_x - margin, shape_buffer.top_y - margin),
                (shape_buffer.right_x + margin, shape_buffer.top_y - margin),
                (shape_buffer.right_x + margin, shape_buffer.bottom_y + margin),
                (shape_buffer.left_x - margin, shape_buffer.bottom_y + margin),
            ]
        )

    def get_closest_side(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
    ) -> ShapeSide:
        direct_line = LineString([shape_buffer.center.shapely, target_point.shapely])
        node_polygon = self.polygon(shape_buffer)
        intersection = direct_line.intersection(node_polygon)
        intersection_point = intersection.line_interpolate_point(1.0, normalized=True)

        closest_side = ShapeSide.TOP
        closest_point, _ = self.get_side_position(
            shape_buffer=shape_buffer,
            side=closest_side,
        )

        closest_distance = intersection_point.distance(closest_point.shapely)

        for side in [ShapeSide.LEFT, ShapeSide.RIGHT, ShapeSide.BOTTOM]:
            point, _ = self.get_side_position(
                shape_buffer=shape_buffer,
                side=side,
            )
            distance = intersection_point.distance(point.shapely)
            if distance < closest_distance:
                closest_distance = distance
                closest_side = side

        return closest_side

    def get_side_position(
        self,
        shape_buffer: "ShapeBuffer",
        side: ShapeSide,
        offset: int = 0,
        extrude: int = 0
    ) -> tuple[Point, Direction]:
        match side:
            case ShapeSide.TOP:
                direction = Direction.UP
                return (
                    Point(x=shape_buffer.center.x + offset, y=shape_buffer.top_y - extrude),
                    direction,
                )
            case ShapeSide.LEFT:
                direction = Direction.LEFT
                return (
                    Point(x=shape_buffer.left_x - extrude, y=shape_buffer.center.y + offset),
                    direction,
                )
            case ShapeSide.BOTTOM:
                direction = Direction.DOWN
                return (
                    Point(x=shape_buffer.center.x - offset, y=shape_buffer.bottom_y + extrude),
                    direction,
                )
            case ShapeSide.RIGHT:
                direction = Direction.RIGHT
                return (
                    Point(x=shape_buffer.right_x + extrude, y=shape_buffer.center.y - offset),
                    direction,
                )
        raise RuntimeError(side)


class JustContentShape(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        properties: ShapeProperties,
        port_side_assignments: dict[ShapeSide, list[str]] = dict(),
    ) -> list[Strip]:
        # TODO Add padding and allow for ports
        return self._renderable_type_to_strips(console, content_renderable)


@dataclass(kw_only=True)
class ShapeBuffer(StripBuffer):
    center: Point
    shape: Shape = JustContentShape()

    shape_width: int
    shape_height: int

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
        return self.shape_width

    @property
    def height(self) -> int:
        return self.shape_height
