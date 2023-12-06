from typing import Any, Protocol, cast

from rich.console import Console, RenderableType
from rich.padding import PaddingDimensions
from rich.segment import Segment
from rich.style import Style

from netext.geometry import Magnet, Point
from shapely import LineString, Polygon
from netext.geometry.magnet import ShapeSide

from netext.rendering.segment_buffer import Strip, Spacer
import math
from dataclasses import dataclass
from netext.rendering.segment_buffer import StripBuffer


class Shape(Protocol):
    def get_magnet_position(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
        magnet: Magnet,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> tuple[Point, Point | None]:
        return NotImplemented

    def get_closest_magnet(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> Magnet:
        return NotImplemented

    def polygon(self, shape_buffer: "ShapeBuffer", margin: float = 0) -> Polygon:
        return NotImplemented

    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        data: dict[str, Any],
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

    def get_closest_magnet(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> Magnet:
        direct_line = LineString([shape_buffer.center.shapely, target_point.shapely])
        node_polygon = self.polygon(shape_buffer)
        intersection = direct_line.intersection(node_polygon)
        intersection_point = intersection.line_interpolate_point(1.0, normalized=True)

        closest_magnet = Magnet.TOP
        closest_point, _ = self.get_magnet_position(
            shape_buffer=shape_buffer,
            target_point=target_point,
            magnet=closest_magnet,
            offset=offset,
            extrusion_offset=extrusion_offset,
        )

        closest_distance = intersection_point.distance(closest_point.shapely)

        for magnet in [Magnet.LEFT, Magnet.RIGHT, Magnet.BOTTOM]:
            point, _ = self.get_magnet_position(
                shape_buffer=shape_buffer,
                target_point=target_point,
                magnet=magnet,
                offset=offset,
                extrusion_offset=extrusion_offset,
            )
            distance = intersection_point.distance(point.shapely)
            if distance < closest_distance:
                closest_distance = distance
                closest_magnet = magnet

        return closest_magnet

    def get_magnet_position(
        self,
        shape_buffer: "ShapeBuffer",
        target_point: Point,
        magnet: Magnet,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> tuple[Point, Point | None]:
        extruded_point: Point | None = None
        match magnet:
            case Magnet.TOP:
                extruded_point = Point(
                    x=shape_buffer.center.x + offset,
                    y=shape_buffer.top_y - extrusion_offset,
                )
                return (
                    Point(x=shape_buffer.center.x + offset, y=shape_buffer.top_y),
                    extruded_point,
                )
            case Magnet.LEFT:
                extruded_point = Point(
                    x=shape_buffer.left_x - extrusion_offset,
                    y=shape_buffer.center.y + offset,
                )
                return (
                    Point(x=shape_buffer.left_x, y=shape_buffer.center.y + offset),
                    extruded_point,
                )
            case Magnet.BOTTOM:
                extruded_point = Point(
                    x=shape_buffer.center.x - offset,
                    y=shape_buffer.bottom_y + extrusion_offset,
                )
                return (
                    Point(x=shape_buffer.center.x - offset, y=shape_buffer.bottom_y),
                    extruded_point,
                )
            case Magnet.RIGHT:
                extruded_point = Point(
                    x=shape_buffer.right_x + extrusion_offset,
                    y=shape_buffer.center.y - offset,
                )
                return (
                    Point(x=shape_buffer.right_x, y=shape_buffer.center.y - offset),
                    extruded_point,
                )
            case Magnet.CENTER:
                return shape_buffer.center - Point(x=offset, y=0), None
            case Magnet.CLOSEST:
                direct_line = LineString([shape_buffer.center.shapely, target_point.shapely])
                node_polygon = self.polygon(shape_buffer)
                intersection = direct_line.intersection(node_polygon)
                intersection_point = intersection.line_interpolate_point(1.0, normalized=True)

                closest_magnet = Magnet.TOP
                closest_point, closest_extruded_point = self.get_magnet_position(
                    shape_buffer=shape_buffer,
                    target_point=target_point,
                    magnet=closest_magnet,
                    offset=offset,
                    extrusion_offset=extrusion_offset,
                )

                closest_distance = intersection_point.distance(closest_point.shapely)

                for magnet in [Magnet.LEFT, Magnet.RIGHT, Magnet.BOTTOM]:
                    point, extruded_point = self.get_magnet_position(
                        shape_buffer=shape_buffer,
                        target_point=target_point,
                        magnet=magnet,
                        offset=offset,
                        extrusion_offset=extrusion_offset,
                    )
                    distance = intersection_point.distance(point.shapely)
                    if distance < closest_distance:
                        closest_point = point
                        closest_extruded_point = extruded_point
                        closest_distance = distance

                return closest_point, closest_extruded_point
        raise RuntimeError(magnet)


class JustContent(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        data: dict[str, Any],
        port_side_assignments: dict[ShapeSide, list[str]] = dict(),
    ) -> list[Strip]:
        # TODO Add padding and allow for ports
        return self._renderable_type_to_strips(console, content_renderable)


@dataclass(kw_only=True)
class ShapeBuffer(StripBuffer):
    center: Point
    shape: Shape = JustContent()

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
