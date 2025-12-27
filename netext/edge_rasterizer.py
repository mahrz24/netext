from dataclasses import dataclass
from typing import Hashable

from rich.console import Console
from rich.style import Style
from netext.edge_rendering.arrow_tips import render_arrow_tip_buffers
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rendering.path_rasterizer import rasterize_edge_path
from netext.edge_routing.edge import EdgeInput
from netext.edge_routing.route import route_edge, route_edges
from netext.geometry.magnet import Magnet, ShapeSide

from netext.node_rendering.buffers import EdgeLabelBuffer, NodeBuffer
from netext.properties.edge import EdgeProperties
from netext.properties.shape import JustContent
from netext.shapes.shape import JustContentShape
from netext.rendering.segment_buffer import Layer, StripBuffer, ZIndex
import netext._core as core
from netext._core import DirectedPoint


@dataclass
class EdgeRoutingRequest:
    u: Hashable
    v: Hashable
    u_buffer: NodeBuffer
    v_buffer: NodeBuffer
    properties: EdgeProperties
    lod: int = 1


def rasterize_edges(
    console: Console,
    edge_router: core.EdgeRouter,
    edge_route_requests: list[EdgeRoutingRequest],
    layout_direction: core.LayoutDirection | None = None,
) -> tuple[
    dict[tuple[Hashable, Hashable], EdgeBuffer],
    dict[tuple[Hashable, Hashable], list[StripBuffer]],
]:
    edge_inputs = []
    edge_anchors = []

    for request in edge_route_requests:
        if not request.properties.show:
            continue

        if request.lod != 1:
            request.properties = request.properties.lod_properties.get(request.lod, request.properties)

        start, end = determine_edge_anchors(
            request.u_buffer, request.v_buffer, request.properties, layout_direction=layout_direction
        )
        edge_input = EdgeInput(
            start=start.point,
            end=end.point,
            label=request.properties.label,
            routing_mode=request.properties.routing_mode,
            edge_segment_drawing_mode=request.properties.segment_drawing_mode,
        )
        edge_inputs.append(edge_input)
        edge_anchors.append((request.u, request.v, start, end, request.properties.routing_mode))

    edge_paths = route_edges(edge_router, edge_anchors)

    edge_buffers = dict()
    label_buffers = dict()

    for edge_index, (request, edge_input, edge_path) in enumerate(zip(edge_route_requests, edge_inputs, edge_paths)):
        if not edge_path.directed_points or edge_path.start == edge_path.end:
            continue

        strips, edge_label_buffers, boundary_1, boundary_2 = rasterize_path_and_label(
            console, request.u_buffer, request.v_buffer, request.properties, edge_input, edge_path
        )

        if boundary_1 == boundary_2:
            continue

        z_index = ZIndex(layer=Layer.EDGES, layer_index=edge_index)

        edge_buffer = EdgeBuffer(
            path=edge_path,
            edge=(request.u_buffer.node, request.v_buffer.node),
            z_index=z_index,
            boundary_1=boundary_1,
            boundary_2=boundary_2,
            strips=strips,
        )

        edge_buffers[(request.u, request.v)] = edge_buffer
        label_buffers[(request.u, request.v)] = edge_label_buffers

    return edge_buffers, label_buffers


def rasterize_edge(
    console: Console,
    edge_router: core.EdgeRouter,
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    properties: EdgeProperties,
    lod: int = 1,
    edge_index: int = 0,
    layout_direction: core.LayoutDirection | None = None,
) -> tuple[EdgeBuffer, list[StripBuffer]] | None:
    if not properties.show:
        return None

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    (
        start,
        end,
    ) = determine_edge_anchors(u_buffer, v_buffer, properties, layout_direction)

    edge_input = EdgeInput(
        start=start.point,
        end=end.point,
        label=properties.label,
        routing_mode=properties.routing_mode,
        edge_segment_drawing_mode=properties.segment_drawing_mode,
    )

    edge_path = route_edge(
        u_buffer.node,
        v_buffer.node,
        start=start,
        end=end,
        edge_router=edge_router,
        edge_routing_mode=properties.routing_mode,
    )

    if not edge_path.directed_points or edge_path.start == edge_path.end:
        return None

    strips, label_buffers, boundary_1, boundary_2 = rasterize_path_and_label(
        console, u_buffer, v_buffer, properties, edge_input, edge_path
    )


    if boundary_1 == boundary_2:
        return None

    z_index = ZIndex(layer=Layer.EDGES, layer_index=edge_index)

    edge_buffer = EdgeBuffer(
        path=edge_path,
        edge=(u_buffer.node, v_buffer.node),
        z_index=z_index,
        boundary_1=boundary_1,
        boundary_2=boundary_2,
        strips=strips,
    )

    return edge_buffer, label_buffers


def rasterize_path_and_label(console, u_buffer, v_buffer, properties, edge_input, edge_path):
    strips = rasterize_edge_path(
        edge_path,
        style=properties.style,
        edge_segment_drawing_mode=properties.segment_drawing_mode,
        dash_pattern=properties.dash_pattern,
    )

    label_buffers: list[StripBuffer] = []

    # TODO Think about this: Shape and node buffer are bound
    # so maybe use the shape to create the node buffer
    # and link it to the creating shape?
    if properties.label is not None:
        shape = JustContentShape()
        label_strips = shape.render_shape(console, properties.label, style=Style(), properties=JustContent(), padding=0)

        label_position = edge_path.distinct_points[round(edge_path.length / 2)]

        label_buffer = EdgeLabelBuffer.from_strips_and_edge(
            label_strips,
            edge=(u_buffer.node, v_buffer.node),
            z_index=ZIndex(layer=Layer.EDGE_LABELS),
            shape=shape,
            center=label_position,
        )
        label_buffers.append(label_buffer)

    label_buffers.extend(
        render_arrow_tip_buffers(
            (u_buffer.node, v_buffer.node),
            properties.end_arrow_tip,
            properties.start_arrow_tip,
            edge_path,
            properties.segment_drawing_mode,
            style=properties.style,
        )
    )

    boundary_1 = edge_path.min_bound
    boundary_2 = edge_path.max_bound

    return strips, label_buffers, boundary_1, boundary_2


def determine_edge_anchors(
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    properties: EdgeProperties,
    layout_direction: core.LayoutDirection | None = None,
) -> tuple[DirectedPoint, DirectedPoint]:
    start = determine_edge_anchor(u_buffer, v_buffer, properties, layout_direction=layout_direction)
    end = determine_edge_anchor(v_buffer, u_buffer, properties, layout_direction=layout_direction)
    return start, end


def determine_edge_anchor(
    buffer: NodeBuffer,
    other_buffer: NodeBuffer,
    properties: EdgeProperties,
    layout_direction: core.LayoutDirection | None = None,
) -> DirectedPoint:
    if (port_name := properties.start_port) is not None and port_name in buffer.node_anchors.all_positions:
        anchor = buffer.node_anchors.all_positions[port_name]
        buffer.connect_port(port_name, other_buffer.node)
    else:
        if buffer.properties.slots and other_buffer.node in buffer.node_anchors.all_positions:
            anchor = buffer.node_anchors.all_positions[other_buffer.node]
        else:
            if properties.start_magnet == Magnet.AUTO:
                side = buffer.determine_edge_side(other_buffer, layout_direction)
            else:
                side = ShapeSide(properties.start_magnet.value)
            anchor = buffer.get_side_position(side, offset=0, extrude=1)
    return anchor
