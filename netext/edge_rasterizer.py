from typing import Hashable

from rich.console import Console
from rich.style import Style
from netext.edge_rendering.arrow_tips import render_arrow_tip_buffers
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rendering.path_rasterizer import rasterize_edge_path
from netext.edge_routing.edge import EdgeLayout
from netext.edge_routing.edge import EdgeInput
from netext.edge_routing.route import route_edge
from netext.geometry.point import Point

from netext.node_rendering.buffers import EdgeLabelBuffer, NodeBuffer
from netext.properties.edge import EdgeProperties
from netext.properties.shape import JustContent
from netext.shapes.shape import JustContentShape
from netext.rendering.segment_buffer import Layer, StripBuffer, ZIndex


def rasterize_edge(
    console: Console,
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    all_nodes: list[NodeBuffer],
    routed_edges: list[EdgeLayout],
    properties: EdgeProperties,
    lod: int = 1,
    edge_layout: EdgeLayout | None = None,
    port_positions: dict[Hashable, dict[str, tuple[Point, Point | None]]] = dict(),
) -> tuple[EdgeBuffer, EdgeLayout, list[StripBuffer]] | None:
    if not properties.show:
        return None

    if lod != 1:
        properties = properties.lod_properties.get(lod, properties)

    if (port_name := properties.start_port) is not None and port_name in port_positions[u_buffer.node]:
        start, start_helper = port_positions[u_buffer.node][port_name]
        u_buffer.connect_port(port_name, v_buffer.node)
    else:
        start, start_helper = u_buffer.get_magnet_position(v_buffer.center, properties.start_magnet)

    if (port_name := properties.end_port) is not None and port_name in port_positions[v_buffer.node]:
        end, end_helper = port_positions[v_buffer.node][port_name]
        v_buffer.connect_port(port_name, u_buffer.node)
    else:
        end, end_helper = v_buffer.get_magnet_position(u_buffer.center, properties.end_magnet)

    edge_input = EdgeInput(
        start=start,
        end=end,
        label=properties.label,
        routing_mode=properties.routing_mode,
        edge_segment_drawing_mode=properties.segment_drawing_mode,
        routing_hints=[],  # TODO: If doing relayout, the edge input should contain the existing segments
    )

    non_start_end_nodes = [node for node in all_nodes if node not in [u_buffer, v_buffer]]

    if edge_layout is None:
        edge_path = route_edge(
            start=start,
            end=end,
            start_helper=start_helper,
            end_helper=end_helper,
            all_nodes=non_start_end_nodes,
            routed_edges=routed_edges,
        )

        # We cut the edge segments with the nodes to get rid of the
        # parts hidden behind the nodes to draw correct arrow tips
        edge_path = edge_path.cut_with_nodes([u_buffer, v_buffer])

        if not edge_path.directed_points or edge_path.start == edge_path.end:
            return None
    else:
        edge_path = edge_layout.path

    strips = rasterize_edge_path(edge_path)

    z_index = ZIndex(layer=Layer.EDGES)

    if routed_edges:
        z_index.layer_index += len(routed_edges)

    edge_layout = EdgeLayout(input=edge_input, path=edge_path, z_index=z_index)

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

    if boundary_1 == boundary_2:
        return None

    edge_buffer = EdgeBuffer(
        path=edge_path,
        edge=(u_buffer.node, v_buffer.node),
        z_index=edge_layout.z_index,
        boundary_1=boundary_1,
        boundary_2=boundary_2,
        strips=strips,
    )

    return edge_buffer, edge_layout, label_buffers
