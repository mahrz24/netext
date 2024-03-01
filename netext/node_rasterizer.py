from collections.abc import Hashable
from typing import Any
import warnings

from rich.console import Console
from rich.padding import Padding
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
    port_side_assignments: dict[ShapeSide, list[str]] = dict(),
) -> NodeBuffer:
    properties = NodeProperties.from_data_dict(data)

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    content_renderable = properties.content_renderer(str(node), data, properties.content_style)

    padding = properties.padding
    if properties.ports:
        # Determine longest padding label length
        # TODO: This can be shape specific and might be moved into the shape like
        # the additional padding on the number of ports
        padding = Padding.unpack(properties.padding)
        additional_top_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in port_side_assignments.get(ShapeSide.TOP, [])
            ]
            + [0]
        )
        additional_left_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in port_side_assignments.get(ShapeSide.LEFT, [])
            ]
            + [0]
        )
        additional_bottom_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
                if port_name in port_side_assignments.get(ShapeSide.BOTTOM, [])
            ]
            + [0]
        )
        additional_right_padding = max(
            [
                len(port.label) + 1
                for port_name, port in properties.ports.items()
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

    match properties.shape:
        case Box():
            shape: Shape = BoxShape()
            shape_props: ShapeProperties = properties.shape
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
        content_renderable,
        style=properties.style,
        padding=padding,
        properties=shape_props,
        port_side_assignments=port_side_assignments,
    )

    return NodeBuffer.from_strips(
        strips,
        node=node,
        properties=properties,
        center=Point(x=0, y=0),
        z_index=ZIndex(layer=Layer.NODES),
        lod=lod,
    )
