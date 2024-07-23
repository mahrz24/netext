from dataclasses import dataclass, field
from typing import Hashable

from rich.console import Console
from rich.style import Style
from netext.edge_rendering.arrow_tips import render_arrow_tip_buffers
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rendering.path_rasterizer import rasterize_edge_path
from netext.edge_routing.edge import EdgeInput
from netext.edge_routing.node_anchors import NodeAnchors
from netext.edge_routing.route import route_edge, route_edges
from netext.geometry.point import Point

from netext.node_rendering.buffers import EdgeLabelBuffer, NodeBuffer
from netext.properties.edge import EdgeProperties
from netext.properties.shape import JustContent
from netext.shapes.shape import JustContentShape
from netext.rendering.segment_buffer import Layer, StripBuffer, ZIndex
import netext._core as core
from netext._core import Direction


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

        start, end, start_direction, end_direction = determine_edge_anchors(
            request.u_buffer, request.v_buffer, request.properties
        )
        edge_input = EdgeInput(
            start=start,
            end=end,
            label=request.properties.label,
            routing_mode=request.properties.routing_mode,
            edge_segment_drawing_mode=request.properties.segment_drawing_mode,
        )
        edge_inputs.append(edge_input)
        edge_anchors.append((request.u, request.v, start, end, start_direction, end_direction, request.properties.routing_mode))

    edge_paths = route_edges(edge_router, edge_anchors)

    edge_buffers = dict()
    label_buffers = dict()

    for request, edge_input, edge_path in zip(edge_route_requests, edge_inputs, edge_paths):
        edge_path = edge_path.cut_with_nodes([request.u_buffer, request.v_buffer])

        if not edge_path.directed_points or edge_path.start == edge_path.end:
            continue

        strips, z_index, edge_label_buffers, boundary_1, boundary_2 = rasterize_path_and_label(
            console, request.u_buffer, request.v_buffer, request.properties, edge_input, edge_path
        )

        if boundary_1 == boundary_2:
            continue

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
) -> tuple[EdgeBuffer, list[StripBuffer]] | None:
    if not properties.show:
        return None

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    start, end, start_direction, end_direction = determine_edge_anchors(u_buffer, v_buffer, properties)

    edge_input = EdgeInput(
        start=start,
        end=end,
        label=properties.label,
        routing_mode=properties.routing_mode,
        edge_segment_drawing_mode=properties.segment_drawing_mode,
    )

    edge_path = route_edge(
        start=start,
        end=end,
        edge_router=edge_router,
        start_direction=start_direction,
        end_direction=end_direction,
        edge_routing_mode=properties.routing_mode
    )

    edge_path = edge_path.cut_with_nodes([u_buffer, v_buffer])

    if not edge_path.directed_points or edge_path.start == edge_path.end:
        return None

    strips, z_index, label_buffers, boundary_1, boundary_2 = rasterize_path_and_label(
        console, u_buffer, v_buffer, properties, edge_input, edge_path
    )

    if boundary_1 == boundary_2:
        return None

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
        edge_path, style=properties.style, edge_segment_drawing_mode=properties.segment_drawing_mode
    )

    z_index = ZIndex(layer=Layer.EDGES)

    # TODO Need to add this back in somehow
    # if routed_edges:
    #     z_index.layer_index += len(routed_edges)

    label_buffers: list[StripBuffer] = []

    # TODO Think about this: Shape and node buffer are bound
    # so maybe use the shape to create the node buffer
    # and link it to the creating shape?
    if properties.label is not None:
        shape = JustContentShape()
        label_strips = shape.render_shape(console, properties.label, style=Style(), properties=JustContent(), padding=0)

        label_position = edge_path.edge_iter_point(round(edge_path.length / 2))

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

    return strips, z_index, label_buffers, boundary_1, boundary_2


def determine_edge_anchors(
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    properties: EdgeProperties,
) -> tuple[Point, Point, Direction, Direction]:
    if (port_name := properties.start_port) is not None and port_name in u_buffer.node_anchors.all_positions:
        start, start_direction = u_buffer.node_anchors.all_positions[port_name]
        u_buffer.connect_port(port_name, v_buffer.node)
    else:
        start, start_direction = u_buffer.get_magnet_position(v_buffer.center, properties.start_magnet)

    if (port_name := properties.end_port) is not None and port_name in v_buffer.node_anchors.all_positions:
        end, end_direction = v_buffer.node_anchors.all_positions[port_name]
        v_buffer.connect_port(port_name, u_buffer.node)
    else:
        end, end_direction = v_buffer.get_magnet_position(u_buffer.center, properties.end_magnet)

    return start, end, start_direction, end_direction
