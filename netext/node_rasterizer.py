from collections.abc import Hashable
from typing import Any, cast
import warnings

from rich.console import Console
from rich.padding import Padding
from netext.geometry import Point
from netext.geometry.magnet import ShapeSide
from netext.node_rendering.buffers import NodeBuffer
from netext.properties.node import NodeProperties
from netext.properties.shape import BoxProperties, JustContentProperties, ShapeProperties
from netext.shapes.box import Box
from netext.shapes.shape import JustContent, Shape


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

    properties: NodeProperties = cast(NodeProperties, data.get("$properties", NodeProperties.from_attribute_dict(data)))

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    content_renderable = properties.content_renderer(str(node), data, properties.content_style)

    padding = properties.padding
    if "$ports" in data:
        # Determine longest padding label length
        # TODO: This can be shape specific and might be moved into the shape like
        # the additional padding on the number of ports
        padding = Padding.unpack(properties.padding)
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

    match properties.shape:
        case BoxProperties():
            shape: Shape = Box()
            shape_props: ShapeProperties = properties.shape
        case JustContentProperties():
            shape = JustContent()
            shape_props = properties.shape
        case Box():
            shape = properties.shape
            shape_props = BoxProperties()
            # This path is deprecated, output deprecation warning
            warnings.warn(
                "Using the Box shape directly is deprecated, use the BoxProperties instead", DeprecationWarning
            )
        case JustContent():
            shape = properties.shape
            shape_props = JustContentProperties()
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
        z_index=-1,
        lod=lod,
    )
