from collections import defaultdict
import math
from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.padding import Padding, PaddingDimensions
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from netext.geometry import Magnet, Point
from shapely import LineString, Polygon
from netext.geometry.magnet import ShapeSide

from netext.rendering.segment_buffer import Reference, Strip, StripBuffer, Spacer


class Shape(Protocol):
    def get_magnet_position(
        self,
        node_buffer: "NodeBuffer",
        target_point: Point,
        magnet: Magnet,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> tuple[Point, Point | None]:
        return NotImplemented

    def get_closest_magnet(
        self,
        node_buffer: "NodeBuffer",
        target_point: Point,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> Magnet:
        return NotImplemented

    def polygon(self, node_buffer: "NodeBuffer", margin: float = 0) -> Polygon:
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

    def get_closest_magnet(
        self,
        node_buffer: "NodeBuffer",
        target_point: Point,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> Magnet:
        direct_line = LineString([node_buffer.center.shapely, target_point.shapely])
        node_polygon = self.polygon(node_buffer)
        intersection = direct_line.intersection(node_polygon)
        intersection_point = intersection.line_interpolate_point(1.0, normalized=True)

        closest_magnet = Magnet.TOP
        closest_point, _ = self.get_magnet_position(
            node_buffer=node_buffer,
            target_point=target_point,
            magnet=closest_magnet,
            offset=offset,
            extrusion_offset=extrusion_offset,
        )

        closest_distance = intersection_point.distance(closest_point.shapely)

        for magnet in [Magnet.LEFT, Magnet.RIGHT, Magnet.BOTTOM]:
            point, _ = self.get_magnet_position(
                node_buffer=node_buffer,
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
        node_buffer: "NodeBuffer",
        target_point: Point,
        magnet: Magnet,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> tuple[Point, Point | None]:
        extruded_point: Point | None = None
        match magnet:
            case Magnet.TOP:
                extruded_point = Point(
                    x=node_buffer.center.x + offset,
                    y=node_buffer.top_y - extrusion_offset,
                )
                return (
                    Point(x=node_buffer.center.x + offset, y=node_buffer.top_y),
                    extruded_point,
                )
            case Magnet.LEFT:
                extruded_point = Point(
                    x=node_buffer.left_x - extrusion_offset,
                    y=node_buffer.center.y + offset,
                )
                return (
                    Point(x=node_buffer.left_x, y=node_buffer.center.y + offset),
                    extruded_point,
                )
            case Magnet.BOTTOM:
                extruded_point = Point(
                    x=node_buffer.center.x - offset,
                    y=node_buffer.bottom_y + extrusion_offset,
                )
                return (
                    Point(x=node_buffer.center.x - offset, y=node_buffer.bottom_y),
                    extruded_point,
                )
            case Magnet.RIGHT:
                extruded_point = Point(
                    x=node_buffer.right_x + extrusion_offset,
                    y=node_buffer.center.y - offset,
                )
                return (
                    Point(x=node_buffer.right_x, y=node_buffer.center.y - offset),
                    extruded_point,
                )
            case Magnet.CENTER:
                return node_buffer.center - Point(x=offset, y=0), None
            case Magnet.CLOSEST:
                direct_line = LineString(
                    [node_buffer.center.shapely, target_point.shapely]
                )
                node_polygon = self.polygon(node_buffer)
                intersection = direct_line.intersection(node_polygon)
                intersection_point = intersection.line_interpolate_point(
                    1.0, normalized=True
                )

                closest_magnet = Magnet.TOP
                closest_point, closest_extruded_point = self.get_magnet_position(
                    node_buffer=node_buffer,
                    target_point=target_point,
                    magnet=closest_magnet,
                    offset=offset,
                    extrusion_offset=extrusion_offset,
                )

                closest_distance = intersection_point.distance(closest_point.shapely)

                for magnet in [Magnet.LEFT, Magnet.RIGHT, Magnet.BOTTOM]:
                    point, extruded_point = self.get_magnet_position(
                        node_buffer=node_buffer,
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


class Box(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        data: dict[str, Any],
        port_side_assignments: dict[ShapeSide, list[str]] = dict(),
    ) -> list[Strip]:
        padding = Padding.unpack(padding)

        box_type = data.get("$box-type", box.ROUNDED)

        # Measure content
        result = self._renderable_type_to_strips(
            console,
            Panel(
                content_renderable,
                expand=False,
                style=style,
                padding=padding,
                box=box_type,
            ),
        )

        height = len(result)
        width = max(
            sum([segment.cell_length for segment in strip.segments]) for strip in result
        )
        rerender = False

        if port_side_assignments:
            if (
                missing_space := width
                - 2
                - max(
                    len(port_side_assignments.get(ShapeSide.TOP, [])),
                    len(port_side_assignments.get(ShapeSide.BOTTOM, [])),
                )
            ) < 0:
                additional_padding = int(math.ceil(-missing_space / 2))
                padding = (
                    padding[0],
                    padding[1] + additional_padding,
                    padding[2],
                    padding[3] + additional_padding,
                )
                rerender = True

            if (
                missing_space := height
                - 2
                - max(
                    len(port_side_assignments.get(ShapeSide.LEFT, [])),
                    len(port_side_assignments.get(ShapeSide.RIGHT, [])),
                )
            ) < 0:
                additional_padding = int(math.ceil(-missing_space / 2))
                padding = (
                    padding[0] + additional_padding,
                    padding[1],
                    padding[2] + additional_padding,
                    padding[3],
                )
                rerender = True

        if rerender:
            result = self._renderable_type_to_strips(
                console,
                Panel(
                    content_renderable,
                    expand=False,
                    style=style,
                    padding=padding,
                    box=box_type,
                ),
            )

        return result


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


@dataclass(kw_only=True)
class PortBuffer(ShapeBuffer):
    port_name: str
    node: Hashable

    @property
    def reference(self) -> Reference | None:
        return Reference(type="port", ref=(self.node, self.port_name))

    @classmethod
    def from_strips_and_node(
        cls,
        strips: list[Strip],
        port_name: str,
        node: Hashable,
        center: Point,
        shape: Shape,
        z_index: int = 0,
    ) -> "PortBuffer":
        width = max(
            sum(segment.cell_length for segment in strip.segments) for strip in strips
        )

        return cls(
            port_name=port_name,
            node=node,
            shape=shape,
            center=center,
            z_index=z_index,
            shape_width=width,
            shape_height=len(strips),
            strips=strips,
        )


@dataclass(kw_only=True)
class PortLabelBuffer(PortBuffer):
    ...


@dataclass(kw_only=True)
class NodeBuffer(ShapeBuffer):
    node: Hashable

    data: dict[str, Any] = field(default_factory=dict)
    margin: int = 0
    lod: int = 1

    port_positions: dict[int, dict[str, tuple[Point, Point | None]]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    ports_per_side: dict[Magnet, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    connected_ports: dict[str, list[Hashable]] = field(
        default_factory=lambda: defaultdict(list)
    )

    @property
    def reference(self) -> Reference | None:
        return Reference(type="node", ref=self.node)

    @classmethod
    def from_strips(
        cls,
        strips: list[Strip],
        node: Hashable,
        center: Point,
        shape: Shape,
        data: dict[str, Any],
        z_index: int = 0,
        margin: int = 0,
        lod: int = 1,
    ) -> "NodeBuffer":
        width = max(
            sum(segment.cell_length for segment in strip.segments) for strip in strips
        )

        return cls(
            node=node,
            data=data,
            shape=shape,
            center=center,
            z_index=z_index,
            shape_width=width,
            shape_height=len(strips),
            strips=strips,
            margin=margin,
            lod=lod,
        )

    def get_magnet_position(
        self,
        target_point: Point,
        magnet: Magnet,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> tuple[Point, Point | None]:
        return self.shape.get_magnet_position(
            self,
            target_point=target_point,
            magnet=magnet,
            offset=offset,
            extrusion_offset=extrusion_offset,
        )

    def get_closest_magnet(
        self,
        target_point: Point,
        offset: int = 0,
        extrusion_offset: int = 2,
    ) -> Magnet:
        return self.shape.get_closest_magnet(
            self,
            target_point=target_point,
            offset=offset,
            extrusion_offset=extrusion_offset,
        )

    @property
    def layout_width(self) -> int:
        return self.width + self.margin * 2

    @property
    def layout_height(self) -> int:
        return self.height + self.margin * 2

    def get_port_position(
        self, port_name: str, port_side: ShapeSide, lod: int, ports_on_side: list[str]
    ) -> tuple[Point, Point | None]:
        # TODO This needs to be moved to the shape, as it's shape specific
        # E.g. the port offset computation makes some assumptions about the border size
        # TODO should we raise on wrong port?
        # TODO more tests for non happy path
        port = self.data.get("$ports", {}).get(port_name, {})

        if port_name in self.port_positions[lod]:
            return self.port_positions[lod][port_name]

        port_index = ports_on_side.index(port_name)

        # TODO 1 is a special case, port should be centered
        if len(ports_on_side) == 1:
            port_offset = 0
        else:
            # TODO Looks a bit weird for odd port numbers as the space is not centered
            if port_side == ShapeSide.TOP or port_side == ShapeSide.BOTTOM:
                port_offset = math.ceil(
                    (float(port_index) / (len(ports_on_side) - 1)) * (self.width - 3)
                ) - math.floor((self.width - 2) / 2)
            else:
                port_offset = math.ceil(
                    (float(port_index) / (len(ports_on_side) - 1)) * (self.height - 3)
                ) - math.floor((self.height - 2) / 2)

        # The magnet has been derived from the shape side, so it's determined and the target point
        # does not matter
        start, start_helper = self.get_magnet_position(
            target_point=Point(0, 0),
            magnet=Magnet(port_side.value),
            offset=port.get("offset", port_offset),
        )
        self.port_positions[lod][port_name] = (start, start_helper)

        return start, start_helper

    def connect_port(self, port_name: str, node: Hashable):
        # TODO check
        self.connected_ports[port_name].append(node)

    def disconnect(self, node: Hashable):
        for port_name in self.connected_ports.keys():
            if node in self.connected_ports[port_name]:
                self.connected_ports[port_name].remove(node)

    def get_port_buffers(
        self,
        console: Console,
        lod: int,
        port_side_assignement: dict[ShapeSide, list[str]],
        port_sides: dict[str, ShapeSide],
    ) -> list[StripBuffer]:
        buffers: list[StripBuffer] = []
        ports = self.data.get("$ports", {})
        for port_name, port_settings in ports.items():
            shape = JustContent()
            port_symbol = port_settings.get("symbol", "○")
            if port_name in self.connected_ports:
                port_symbol = port_settings.get("symbol-connected", "●")
            port_strips = shape.render_shape(
                console, port_symbol, style=Style(), padding=0, data={}
            )

            port_position, port_helper = self.get_port_position(
                port_name=port_name,
                lod=lod,
                ports_on_side=port_side_assignement[port_name],
                port_side=port_sides[port_name],
            )

            port_buffer = PortBuffer.from_strips_and_node(
                port_strips,
                port_name=port_name,
                node=self.node,
                # TODO Z indices need a layer concept
                z_index=-2,
                shape=shape,
                center=port_position,
            )
            buffers.append(port_buffer)

            # The second should always be not None
            if (
                port_label := port_settings.get("label", None)
            ) is not None and port_helper is not None:
                # This does not work well with unicode chars, use rich methods here instead
                port_label_length = len(port_label)
                if port_sides[port_name] in [ShapeSide.TOP, ShapeSide.BOTTOM]:
                    port_label = "\n".join([c for c in port_label])
                port_label_strips = shape.render_shape(
                    console, port_label, style=Style(), padding=0, data={}
                )

                normalizer = port_helper.distance_to(port_position)

                offset: float = 1
                if port_sides[port_name] in [ShapeSide.BOTTOM, ShapeSide.TOP]:
                    offset = 0.5
                label_position = port_position - (port_helper - port_position) * (
                    1.0 / normalizer * ((port_label_length) * 0.5 + offset)
                )
                port_label_buffer = PortLabelBuffer.from_strips_and_node(
                    port_label_strips,
                    port_name=port_name,
                    node=self.node,
                    # TODO Z indices need a layer concept
                    z_index=-2,
                    shape=shape,
                    center=label_position,
                )
                buffers.append(port_label_buffer)

        return buffers


def _default_content_renderer(
    node_str: str, data: dict[str, Any], content_style: Style
) -> RenderableType:
    return Text(node_str, style=content_style)


def rasterize_node(
    console: Console,
    node: Hashable,
    data: dict[str, Any],
    lod: int = 1,
    port_side_assignments: dict[ShapeSide, list[str]] = dict(),
) -> NodeBuffer:
    # TODO make helper function to get node from data
    to_be_ignored = []
    for key, val in data.items():
        if val is None:
            to_be_ignored.append(key)
    for key in to_be_ignored:
        del data[key]
    shape: Shape = data.get("$shape", Box())
    style: Style = data.get("$style", Style())
    content_style = data.get("$content-style", Style())
    margin: int = data.get("$margin", 0)
    padding: PaddingDimensions = data.get("$padding", (0, 1))
    # TODO Cache content renderer for rerendering due to port existing
    content_renderer = data.get("$content-renderer", _default_content_renderer)
    content_renderable = content_renderer(str(node), data, content_style)

    if lod != 1:
        shape = data.get(f"$shape-{lod}", shape)
        style = data.get(f"$style-{lod}", style)
        content_style = data.get(f"$content-style-{lod}", content_style)
        margin = data.get(f"$margin-{lod}", margin)
        padding = data.get(f"$margin-{lod}", 0)
        content_renderer = data.get(f"$content-renderer-{lod}", content_renderer)
        content_renderable = content_renderer(str(node), data, content_style)

    if "$ports" in data:
        # Determine longest padding label length
        # TODO: This can be shape specific and might be moved into the shape like
        # the additional padding on the number of ports
        padding = Padding.unpack(padding)
        additional_top_padding = max(
            [
                len(port["label"]) + 1
                for port_name, port in data["$ports"].items()
                if port_name in port_side_assignments.get(ShapeSide.TOP, [])
            ]
            + [0]
        )
        additional_left_padding = max(
            [
                len(port["label"]) + 1
                for port_name, port in data["$ports"].items()
                if port_name in port_side_assignments.get(ShapeSide.LEFT, [])
            ]
            + [0]
        )
        additional_bottom_padding = max(
            [
                len(port["label"]) + 1
                for port_name, port in data["$ports"].items()
                if port_name in port_side_assignments.get(ShapeSide.BOTTOM, [])
            ]
            + [0]
        )
        additional_right_padding = max(
            [
                len(port["label"]) + 1
                for port_name, port in data["$ports"].items()
                if port_name in port_side_assignments.get(ShapeSide.RIGHT, [])
            ]
            + [0]
        )
        padding = (
            padding[0] + additional_top_padding,
            padding[1] + additional_right_padding,
            padding[2] + additional_bottom_padding,
            padding[3] + additional_left_padding,
        )

    strips = shape.render_shape(
        console,
        content_renderable,
        style=style,
        padding=padding,
        data=data,
        port_side_assignments=port_side_assignments,
    )

    return NodeBuffer.from_strips(
        strips,
        data=data,
        node=node,
        center=Point(x=0, y=0),
        z_index=-1,
        shape=shape,
        margin=margin,
        lod=lod,
    )


@dataclass(kw_only=True)
class EdgeLabelBuffer(ShapeBuffer):
    edge: tuple[Hashable, Hashable]

    @property
    def reference(self) -> Reference | None:
        return Reference(type="edge_label", ref=self.edge)

    @classmethod
    def from_strips_and_edge(
        cls,
        strips: list[Strip],
        edge: tuple[Hashable, Hashable],
        center: Point,
        shape: Shape,
        z_index: int = 0,
    ) -> "EdgeLabelBuffer":
        width = max(
            sum(segment.cell_length for segment in strip.segments) for strip in strips
        )

        return cls(
            edge=edge,
            shape=shape,
            center=center,
            z_index=z_index,
            shape_width=width,
            shape_height=len(strips),
            strips=strips,
        )
