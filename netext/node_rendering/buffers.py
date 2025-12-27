from collections import defaultdict
import math
from collections.abc import Hashable
from dataclasses import dataclass, field
from typing_extensions import Self

from rich.console import Console
from rich.style import Style

from netext._core import Point, DirectedPoint
from netext.edge_routing.node_anchors import NodeAnchors
from netext.geometry import Magnet
from netext.geometry.magnet import ShapeSide
from netext.properties.edge import EdgeProperties
from netext.properties.node import NodeProperties, Port
from netext.properties.shape import JustContent

from netext.rendering.segment_buffer import Layer, Reference, Strip, StripBuffer, ZIndex
from netext.shapes.shape import JustContentShape, Shape, ShapeBuffer

import netext._core as core


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
        z_index: ZIndex = ZIndex(layer=Layer.PORTS),
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
class PortLabelBuffer(PortBuffer): ...


@dataclass(kw_only=True)
class RoutingHints:
    density_in_layout_direction: float = 0.0
    relative_offset_in_layout_direction: float = 0.0


@dataclass(kw_only=True)
class NodeBuffer(ShapeBuffer):
    node: Hashable

    routing_hints: RoutingHints = field(default_factory=RoutingHints)

    properties: NodeProperties = field(default_factory=lambda: NodeProperties())
    margin: int = 0
    lod: int = 1

    node_anchors: NodeAnchors = field(default_factory=lambda: NodeAnchors())
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
        z_index: ZIndex = ZIndex(layer=Layer.NODES),
        lod: int = 1,
        node_anchors: NodeAnchors = NodeAnchors(),
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
            node_anchors=node_anchors,
        )

    def get_side_position(
        self,
        side: ShapeSide,
        offset: int = 0,
        extrude: int = 0,
    ) -> DirectedPoint:
        return self.shape.get_side_position(
            self,
            side=side,
            offset=offset,
            extrude=extrude,
        )

    def get_closest_side(
        self,
        target_point: Point,
    ) -> ShapeSide:
        return self.shape.get_closest_side(
            self,
            target_point=target_point,
        )

    @property
    def layout_width(self) -> int:
        return self.width + self.margin * 2

    @property
    def layout_height(self) -> int:
        return self.height + self.margin * 2

    def determine_edge_sides(
        self,
        out_neighbors: list[tuple[Self, EdgeProperties]] | None = None,
        in_neighbors: list[tuple[Self, EdgeProperties]] | None = None,
        layout_direction: core.LayoutDirection | None = None,
    ) -> None:
        out_neighbors = out_neighbors or []
        in_neighbors = in_neighbors or []

        if self.properties.slots:
            for v_buffer, props in out_neighbors:
                if props.start_port is None:
                    if props.start_magnet == Magnet.AUTO:
                        edge_side = self.determine_edge_side(v_buffer, layout_direction)
                    else:
                        edge_side = ShapeSide(props.start_magnet.value)
                    self.node_anchors.edge_sides[(self.node, v_buffer.node)] = edge_side
                    sort_key = (
                        -v_buffer.center.y if edge_side in [ShapeSide.LEFT, ShapeSide.RIGHT] else -v_buffer.center.x
                    )
                    self.node_anchors.edges_per_side[edge_side].append((sort_key, v_buffer.node))
            for u_buffer, props in in_neighbors:
                if props.start_magnet == Magnet.AUTO:
                    edge_side = self.determine_edge_side(u_buffer, layout_direction)
                else:
                    edge_side = ShapeSide(props.start_magnet.value)
                self.node_anchors.edge_sides[(u_buffer.node, self.node)] = edge_side
                sort_key = u_buffer.center.y if edge_side in [ShapeSide.LEFT, ShapeSide.RIGHT] else u_buffer.center.x
                self.node_anchors.edges_per_side[edge_side].append((sort_key, u_buffer.node))

        for current_port_name, port in sorted(self.properties.ports.items(), key=lambda x: x[1].key):
            if port.magnet == Magnet.AUTO or port.magnet is None:
                port_side = ShapeSide.LEFT
                for v_buffer, props in out_neighbors:
                    if props.start_port == current_port_name:
                        port_side = self.get_closest_side(v_buffer.center)
                for u_buffer, props in in_neighbors:
                    if props.end_port == current_port_name:
                        port_side = self.get_closest_side(u_buffer.center)
            else:
                port_side = ShapeSide(port.magnet.value)
            self.node_anchors.port_sides[current_port_name] = port_side
            self.node_anchors.ports_per_side[port_side].append(current_port_name)

    def determine_edge_side(
        self, other_buffer: "NodeBuffer", layout_direction: core.LayoutDirection | None
    ) -> ShapeSide:
        if layout_direction == core.LayoutDirection.TOP_DOWN:
            # Prefer top or bottom, then left or right
            # First check if the other buffer is above or below
            if other_buffer.bottom_y < self.top_y:
                side = ShapeSide.TOP
            elif other_buffer.top_y > self.bottom_y:
                side = ShapeSide.BOTTOM
            elif other_buffer.left_x < self.right_x:
                side = ShapeSide.LEFT
            else:
                side = ShapeSide.RIGHT
        elif layout_direction == core.LayoutDirection.LEFT_RIGHT:
            if other_buffer.right_x < self.left_x:
                side = ShapeSide.LEFT
            elif other_buffer.left_x > self.right_x:
                side = ShapeSide.RIGHT
            elif other_buffer.top_y < self.bottom_y:
                side = ShapeSide.BOTTOM
            else:
                side = ShapeSide.TOP
            side = self.get_closest_side(other_buffer.center)
        else:
            side = self.get_closest_side(other_buffer.center)
        return side

    def determine_edge_positions(self) -> None:
        for current_port_name, _ in sorted(self.properties.ports.items(), key=lambda x: x[1].key):
            port_side = self.node_anchors.port_sides[current_port_name]
            slotted_edges_on_side = len(self.node_anchors.edges_per_side[port_side])
            pos = self.get_port_position(
                port_name=current_port_name,
                port_side=port_side,
                ports_on_side=self.node_anchors.ports_per_side[port_side],
                slotted_edges_on_side=slotted_edges_on_side,
            )
            self.node_anchors.all_positions[current_port_name] = pos
            self.node_anchors.port_positions[current_port_name] = pos.point

        for side in [ShapeSide.TOP, ShapeSide.LEFT, ShapeSide.BOTTOM, ShapeSide.RIGHT]:
            edges_on_side = len(self.node_anchors.edges_per_side[side])
            ports_on_side = len(self.node_anchors.ports_per_side[side])
            edges_on_side += ports_on_side

            for edge_index, (sort_key, edge) in enumerate(sorted(self.node_anchors.edges_per_side[side])):
                if edges_on_side == 1:
                    edge_offset = 0
                else:
                    # TODO Duplication with port offset computation
                    # Also should be moved to the shape

                    edges_to_distribute = ports_on_side + edges_on_side
                    slot_fraction = float(ports_on_side + edge_index) / (edges_to_distribute-1)

                    if side == ShapeSide.TOP or side == ShapeSide.BOTTOM:
                        available_width = self.width - 2
                        remainder = available_width % edges_to_distribute
                        remaining_width = available_width - remainder - 1
                        edge_offset = math.floor(
                            (slot_fraction * remaining_width)) - (remaining_width // 2)
                        if side == ShapeSide.TOP:
                            edge_offset -= 1
                    else:
                        available_height = self.height - 2
                        remainder = available_height % edges_to_distribute
                        remaining_height = available_height - remainder - 1
                        edge_offset = math.floor(
                            (slot_fraction * remaining_height)) - (remaining_height // 2)
                        if side == ShapeSide.LEFT:
                            edge_offset -= 1

                start = self.get_side_position(
                    side,
                    offset=edge_offset,
                    extrude=1,
                )
                self.node_anchors.all_positions[edge] = start

    def get_port_position(
        self, port_name: str, port_side: ShapeSide, ports_on_side: list[str], slotted_edges_on_side: int = 0
    ) -> DirectedPoint:
        # TODO This needs to be moved to the shape, as it's shape specific
        # E.g. the port offset computation makes some assumptions about the border size
        # TODO should we raise on wrong port?
        # TODO more tests for non happy path
        port = self.properties.ports.get(port_name, Port())

        if port_name in self.node_anchors.all_positions:
            return self.node_anchors.all_positions[port_name]

        port_index = ports_on_side.index(port_name)

        edges_on_side = len(ports_on_side) + slotted_edges_on_side

        # TODO 1 is a special case, port should be centered
        if edges_on_side == 1:
            port_offset = 0
        else:
            # TODO Looks a bit weird for odd port numbers as the space is not centered
            if port_side == ShapeSide.TOP or port_side == ShapeSide.BOTTOM:
                port_offset = math.ceil((float(port_index) / (edges_on_side - 1)) * (self.width - 3)) - math.floor(
                    (self.width - 2) / 2
                )
            else:
                port_offset = math.ceil((float(port_index) / (edges_on_side - 1)) * (self.height - 3)) - math.floor(
                    (self.height - 2) / 2
                )

        # The magnet has been derived from the shape side, so it's determined and the target point
        # does not matter
        start = self.get_side_position(
            side=port_side,
            offset=port.offset or port_offset,
        )
        self.node_anchors.all_positions[port_name] = start

        return start

    def connect_port(self, port_name: str, node: Hashable):
        # TODO check if already connected
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
    ) -> list[StripBuffer]:
        buffers: list[StripBuffer] = []
        ports = self.properties.ports
        for port_name, port in ports.items():
            shape = JustContentShape()
            # TODO Check if the symbol default should be moved to the property as it is not dynamic
            # Only dynamic defaults should be nullable.
            port_symbol = port.symbol
            if port_name in self.connected_ports:
                port_symbol = port.symbol_connected
            port_strips = shape.render_shape(console, port_symbol, style=Style(), padding=0, properties=JustContent())

            port_position, _ = self.get_port_position(
                port_name=port_name,
                ports_on_side=self.node_anchors.ports_per_side[self.node_anchors.port_sides[port_name]],
                port_side=self.node_anchors.port_sides[port_name],
            )

            port_buffer = PortBuffer.from_strips_and_node(
                port_strips,
                port_name=port_name,
                node=self.node,
                shape=shape,
                center=port_position,
            )
            buffers.append(port_buffer)

            port_label = port.label
            # TODO: This does not work well with unicode chars, use rich methods here instead
            port_label_length = len(port.label)

            if self.node_anchors.port_sides[port_name] in [ShapeSide.TOP, ShapeSide.BOTTOM]:
                port_label = "\n".join([c for c in port.label])

            port_label_strips = shape.render_shape(
                console, port_label, style=Style(), padding=0, properties=JustContent()
            )

            match self.node_anchors.port_sides[port_name]:
                case ShapeSide.TOP:
                    label_position = Point(x=port_position.x, y=port_position.y + port_label_length // 2 + 1)
                case ShapeSide.LEFT:
                    label_position = Point(x=port_position.x + port_label_length // 2 + 2, y=port_position.y)
                case ShapeSide.BOTTOM:
                    label_position = Point(x=port_position.x, y=port_position.y - port_label_length // 2 - 1)
                case ShapeSide.RIGHT:
                    label_position = Point(x=port_position.x - port_label_length // 2 - 2, y=port_position.y)

            port_label_buffer = PortLabelBuffer.from_strips_and_node(
                port_label_strips,
                port_name=port_name,
                node=self.node,
                shape=shape,
                z_index=ZIndex(layer=Layer.PORT_LABELS),
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
        z_index: ZIndex = ZIndex(layer=Layer.EDGE_LABELS),
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
