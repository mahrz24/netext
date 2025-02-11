from collections.abc import Hashable
from typing import Any
import warnings

from rich.console import Console
from rich.padding import Padding
from netext.edge_routing.node_anchors import NodeAnchors
from netext.geometry import Point
from netext.geometry.magnet import ShapeSide
from netext.node_rendering.buffers import NodeBuffer
from netext.properties.node import NodeProperties
from netext.properties.shape import Box, JustContent, ShapeProperties
from netext.rendering.segment_buffer import Layer, ZIndex
from netext.shapes.box import BoxShape
from netext.shapes.shape import JustContentShape, Shape


def rasterize_node(
    console: Console,
    node: Hashable,
    data: dict[str, Any],
    lod: int = 1,
    node_anchors: NodeAnchors | None = None,
) -> NodeBuffer:
    properties = NodeProperties.from_data_dict(data)

    if node_anchors is None:
        node_anchors = NodeAnchors()

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    content_renderable = properties.content_renderer(str(node), data, properties.content_style)

    padding = properties.padding
    if properties.ports or properties.shape:
        # Determine longest padding label length
        # TODO: This can be shape specific and might be moved into the shape like
        # the additional padding on the number of ports
        padding = Padding.unpack(properties.padding)
        additional_top_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in node_anchors.ports_per_side.get(ShapeSide.TOP, [])
            ]
            + [
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.LEFT])
                    + len(node_anchors.edges_per_side.get(ShapeSide.LEFT, []))
                )
                // 2,
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.RIGHT])
                    + len(node_anchors.edges_per_side.get(ShapeSide.RIGHT, []))
                )
                // 2,
            ]
        )
        additional_left_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in node_anchors.ports_per_side.get(ShapeSide.LEFT, [])
            ]
            + [
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.TOP])
                    + len(node_anchors.edges_per_side.get(ShapeSide.TOP, []))
                )
                // 2,
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.BOTTOM])
                    + len(node_anchors.edges_per_side.get(ShapeSide.BOTTOM, []))
                )
                // 2,
            ]
        )
        additional_bottom_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in node_anchors.ports_per_side.get(ShapeSide.BOTTOM, [])
            ]
            + [
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.LEFT])
                    + len(node_anchors.edges_per_side.get(ShapeSide.LEFT, []))
                )
                // 2,
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.RIGHT])
                    + len(node_anchors.edges_per_side.get(ShapeSide.RIGHT, []))
                )
                // 2,
            ]
        )
        additional_right_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in node_anchors.ports_per_side.get(ShapeSide.RIGHT, [])
            ]
            + [
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.TOP])
                    + len(node_anchors.edges_per_side.get(ShapeSide.TOP, []))
                )
                // 2,
                (
                    len([port for port in properties.ports.values() if port.magnet == ShapeSide.BOTTOM])
                    + len(node_anchors.edges_per_side.get(ShapeSide.BOTTOM, []))
                )
                // 2,
            ]
        )
        padding = (
            padding[0] + additional_top_padding,
            padding[1] + additional_right_padding,
            padding[2] + additional_bottom_padding,
            padding[3] + additional_left_padding,
        )

    shape: Shape = JustContentShape()
    shape_props: ShapeProperties = JustContent()
    match properties.shape:
        case Box():
            shape = BoxShape()
            shape_props = properties.shape
        case JustContent():
            shape = JustContentShape()
            shape_props = properties.shape
        case BoxShape():
            shape = properties.shape
            shape_props = Box()
            # This path is deprecated, output deprecation warning
            warnings.warn(
                "Using the Box shape directly is deprecated, use the BoxProperties instead", DeprecationWarning
            )
        case JustContentShape():
            shape = properties.shape
            shape_props = JustContent()
            warnings.warn(
                "Using the JustContent shape directly is deprecated, use the JustContentProperties instead",
                DeprecationWarning,
            )

    strips = shape.render_shape(
        console,
        width=properties.width,
        height=properties.height,
        content_renderable=content_renderable,
        style=properties.style,
        padding=padding,
        properties=shape_props,
        port_side_assignments=node_anchors.ports_per_side,
    )

    return NodeBuffer.from_strips(
        strips,
        node=node,
        properties=properties,
        center=Point(x=0, y=0),
        z_index=ZIndex(layer=Layer.NODES),
        lod=lod,
        node_anchors=node_anchors,
    )
