from collections import defaultdict
import math
from collections.abc import Hashable
from dataclasses import dataclass, field

from rich.console import Console
from rich.style import Style

from netext.geometry import Magnet, Point
from netext.geometry.magnet import ShapeSide
from netext.properties.node import NodeProperties, Port

from netext.rendering.segment_buffer import Reference, Strip, StripBuffer
from netext.shapes.shape import JustContent, Shape, ShapeBuffer


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
        width = max(sum(segment.cell_length for segment in strip.segments) for strip in strips)

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

    properties: NodeProperties = field(default_factory=lambda: NodeProperties())
    margin: int = 0
    lod: int = 1

    port_positions: dict[int, dict[str, tuple[Point, Point | None]]] = field(default_factory=lambda: defaultdict(dict))
    ports_per_side: dict[Magnet, list[str]] = field(default_factory=lambda: defaultdict(list))

    connected_ports: dict[str, list[Hashable]] = field(default_factory=lambda: defaultdict(list))

    @property
    def reference(self) -> Reference | None:
        return Reference(type="node", ref=self.node)

    @classmethod
    def from_strips(
        cls,
        strips: list[Strip],
        node: Hashable,
        properties: NodeProperties,
        center: Point,
        z_index: int = 0,
        lod: int = 1,
    ) -> "NodeBuffer":
        width = max(sum(segment.cell_length for segment in strip.segments) for strip in strips)

        return cls(
            node=node,
            properties=properties,
            center=center,
            z_index=z_index,
            shape_width=width,
            shape_height=len(strips),
            strips=strips,
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
        port = self.properties.ports.get(port_name, Port())

        if port_name in self.port_positions[lod]:
            return self.port_positions[lod][port_name]

        port_index = ports_on_side.index(port_name)

        # TODO 1 is a special case, port should be centered
        if len(ports_on_side) == 1:
            port_offset = 0
        else:
            # TODO Looks a bit weird for odd port numbers as the space is not centered
            if port_side == ShapeSide.TOP or port_side == ShapeSide.BOTTOM:
                port_offset = math.ceil((float(port_index) / (len(ports_on_side) - 1)) * (self.width - 3)) - math.floor(
                    (self.width - 2) / 2
                )
            else:
                port_offset = math.ceil(
                    (float(port_index) / (len(ports_on_side) - 1)) * (self.height - 3)
                ) - math.floor((self.height - 2) / 2)

        # The magnet has been derived from the shape side, so it's determined and the target point
        # does not matter
        start, start_helper = self.get_magnet_position(
            target_point=Point(0, 0),
            magnet=Magnet(port_side.value),
            offset=port.offset or port_offset,
        )
        self.port_positions[lod][port_name] = (start, start_helper)

        return start, start_helper

    def connect_port(self, port_name: str, node: Hashable):
        # TODO check
        self.connected_ports[port_name].append(node)

    def disconnect(self, node: Hashable):
        ports = list(self.connected_ports.keys())
        for port_name in ports:
            if node in self.connected_ports[port_name]:
                self.connected_ports[port_name].remove(node)
            if not self.connected_ports[port_name]:
                del self.connected_ports[port_name]

    def get_port_buffers(
        self,
        console: Console,
        lod: int,
        port_side_assignement: dict[ShapeSide, list[str]],
        port_sides: dict[str, ShapeSide],
    ) -> list[StripBuffer]:
        buffers: list[StripBuffer] = []
        ports = self.properties.ports
        for port_name, port in ports.items():
            shape = JustContent()
            # TODO Check if the symbol default should be moved to the property as it is not dynamic
            # Only dynamic defaults should be nullable.
            port_symbol = port.symbol
            if port_name in self.connected_ports:
                port_symbol = port.symbol_connected
            port_strips = shape.render_shape(console, port_symbol, style=Style(), padding=0, data={})

            port_position, port_helper = self.get_port_position(
                port_name=port_name,
                lod=lod,
                ports_on_side=port_side_assignement[port_sides[port_name]],
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

            # This should always be not None
            if port_helper is not None:
                port_label = port.label
                # This does not work well with unicode chars, use rich methods here instead
                port_label_length = len(port.label)
                if port_sides[port_name] in [ShapeSide.TOP, ShapeSide.BOTTOM]:
                    port_label = "\n".join([c for c in port.label])
                port_label_strips = shape.render_shape(console, port_label, style=Style(), padding=0, data={})

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
        width = max(sum(segment.cell_length for segment in strip.segments) for strip in strips)

        return cls(
            edge=edge,
            shape=shape,
            center=center,
            z_index=z_index,
            shape_width=width,
            shape_height=len(strips),
            strips=strips,
        )
