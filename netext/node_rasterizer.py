from collections import defaultdict
import math
from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from netext.geometry import Magnet, Point
from shapely import LineString, Polygon

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

    def polygon(self, node_buffer: "NodeBuffer", margin: float = 0) -> Polygon:
        return NotImplemented

    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: int,
        data: dict[str, Any],
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

    # TODO add method that returns the closet magnet
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
                closest_point = point
                closest_distance = distance

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
        padding: int,
        data: dict[str, Any],
    ) -> list[Strip]:
        return self._renderable_type_to_strips(console, content_renderable)


class Box(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        content_renderable: RenderableType,
        style: Style,
        padding: int,
        data: dict[str, Any],
    ) -> list[Strip]:
        box_type = data.get("$box-type", box.ROUNDED)
        return self._renderable_type_to_strips(
            console,
            Panel(
                content_renderable,
                expand=False,
                style=style,
                padding=padding,
                box=box_type,
            ),
        )


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

    data: dict[str, Any]
    margin: int = 0
    lod: int = 1

    port_positions: dict[int, dict[str, tuple[Point, Point | None]]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    ports_per_side: dict[Magnet, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    connected_ports: list[str] = field(default_factory=list)

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

    @property
    def layout_width(self) -> int:
        return self.node_width + self.margin * 2

    @property
    def layout_height(self) -> int:
        return self.node_height + self.margin * 2

    def get_port_position(
        self, port_name: str, target_point: Point, lod: int
    ) -> tuple[Point, Point | None]:
        # TODO should we raise on wrong port?
        # TODO more tests for non happy path
        port = self.data.get("$ports", {}).get(port_name, {})

        if not self.ports_per_side:
            # Count all the ports per side, count closest ports for each side separately
            for port_name, port_settings in sorted(
                self.data.get("$ports", {}).items(), key=lambda x: x[1].get("key", 0)
            ):
                port_magnet = port_settings.get("magnet", Magnet.CLOSEST)
                if port_magnet == Magnet.CENTER:
                    continue
                elif port_magnet == Magnet.CLOSEST:
                    self.ports_per_side[Magnet.TOP].append(port_name)
                    self.ports_per_side[Magnet.BOTTOM].append(port_name)
                    self.ports_per_side[Magnet.LEFT].append(port_name)
                    self.ports_per_side[Magnet.RIGHT].append(port_name)
                else:
                    self.ports_per_side[port_magnet].append(port_name)

        if port_name in self.port_positions[lod]:
            return self.port_positions[lod][port_name]

        start, start_helper = self.get_magnet_position(
            target_point=target_point,
            magnet=port.get("magnet", Magnet.CLOSEST),
            offset=port.get("offset", 0),
        )
        self.port_positions[lod][port_name] = (start, start_helper)

        return start, start_helper

    def connect_port(self, port_name: str):
        # TODO check
        self.connected_ports.append(port_name)

    def get_port_buffers(self, console: Console, lod: int) -> list[StripBuffer]:
        buffers: list[StripBuffer] = []
        for port_name, port_settings in self.data.get("$ports", {}).items():
            shape = JustContent()
            port_symbol = port_settings.get("symbol", "○")
            if port_name in self.connected_ports:
                port_symbol = port_settings.get("symbol", "●")
            port_strips = shape.render_shape(
                console, port_symbol, style=Style(), padding=0, data={}
            )

            port_position, port_helper = self.get_port_position(
                port_name=port_name, target_point=self.center, lod=lod
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

            if (port_label := port_settings.get("label", None)) is not None:
                # TODO depends on the direction of the port
                #  "\n".join([c for c in port_label])
                port_label_strips = shape.render_shape(
                    console, port_label, style=Style(), padding=0, data={}
                )

                # This is inaccurate, and needs to take into account the size of the label
                label_position = port_position - (port_helper - port_position) * 0.5

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
    console: Console, node: Hashable, data: dict[str, Any], lod: int = 1
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
    padding: int = data.get("$padding", 0)
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
        max_padding_length = (
            max(len(port["label"]) for port in data["$ports"].values()) + 1
        )
        padding = max(padding, max_padding_length)

    strips = shape.render_shape(
        console, content_renderable, style=style, padding=padding, data=data
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
