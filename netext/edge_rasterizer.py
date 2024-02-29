from typing import Hashable

from rich.console import Console
from rich.style import Style
from netext.edge_rendering.arrow_tips import render_arrow_tip_buffers
from netext.edge_rendering.bitmap import bitmap_to_strips
from netext.edge_rendering.box import orthogonal_segments_to_strips_with_box_characters
from netext.edge_rendering.bresenham import rasterize_edge_segments
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.edge import EdgeLayout, RoutedEdgeSegments
from netext.edge_routing.edge import EdgeInput
from netext.edge_routing.route import route_edge
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry.index import BufferIndex
from netext.geometry.point import Point

from netext.node_rendering.buffers import EdgeLabelBuffer, NodeBuffer
from netext.properties.edge import EdgeProperties
from netext.properties.shape import JustContentProperties
from netext.shapes.shape import JustContent
from netext.rendering.segment_buffer import StripBuffer


def rasterize_edge(
    console: Console,
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    all_nodes: list[NodeBuffer],
    routed_edges: list[EdgeLayout],
    properties: EdgeProperties,
    node_idx: BufferIndex[NodeBuffer, None] | None = None,
    edge_idx: BufferIndex[EdgeBuffer, EdgeLayout] | None = None,
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

    if edge_layout is None:
        edge_segments = route_edge(
            start=start,
            end=end,
            start_helper=start_helper,
            end_helper=end_helper,
            routing_mode=properties.routing_mode,
            all_nodes=all_nodes,  # non_start_end_nodes,
            routed_edges=routed_edges,
            node_idx=node_idx,
            edge_idx=edge_idx,
        )

        # We cut the edge segments with the nodes to get rid of the
        # parts hidden behind the nodes to draw correct arrow tips
        edge_segments = edge_segments.cut_with_nodes([u_buffer, v_buffer])

        if not edge_segments.segments:
            return None
    else:
        edge_segments = RoutedEdgeSegments(segments=edge_layout.segments, intersections=0)

    if properties.segment_drawing_mode in [
        EdgeSegmentDrawingMode.BOX,
        EdgeSegmentDrawingMode.BOX_ROUNDED,
        EdgeSegmentDrawingMode.BOX_HEAVY,
        EdgeSegmentDrawingMode.BOX_DOUBLE,
        EdgeSegmentDrawingMode.ASCII,
    ]:
        assert (
            properties.routing_mode == EdgeRoutingMode.ORTHOGONAL
        ), "Box characters are only supported on orthogonal lines"
        strips = orthogonal_segments_to_strips_with_box_characters(
            edge_segments.segments, properties.segment_drawing_mode, style=properties.style
        )
    else:
        # In case of pixel / braille we scale and then map character per character
        match properties.segment_drawing_mode:
            case EdgeSegmentDrawingMode.SINGLE_CHARACTER:
                x_scaling = 1
                y_scaling = 1
            case EdgeSegmentDrawingMode.BRAILLE:
                x_scaling = 2
                y_scaling = 4
            case EdgeSegmentDrawingMode.BLOCK:
                x_scaling = 2
                y_scaling = 2
            case _:
                x_scaling = 1
                y_scaling = 1

        bitmap_buffer = rasterize_edge_segments(edge_segments.segments, x_scaling=x_scaling, y_scaling=y_scaling)
        strips = bitmap_to_strips(
            bitmap_buffer,
            edge_segment_drawing_mode=properties.segment_drawing_mode,
            style=properties.style,
        )

    z_index = len(all_nodes) ** 2
    if routed_edges:
        z_index += len(routed_edges)
    edge_layout = EdgeLayout(input=edge_input, segments=edge_segments.segments, z_index=z_index)

    label_buffers: list[StripBuffer] = []

    # TODO Think about this: Shape and node buffer are bound
    # so maybe use the shape to create the node buffer
    # and link it to the creating shape?
    if properties.label is not None:
        shape = JustContent()
        label_strips = shape.render_shape(
            console, properties.label, style=Style(), properties=JustContentProperties(), padding=0
        )

        label_position = edge_segments.edge_iter_point(round(edge_segments.length / 2))

        label_buffer = EdgeLabelBuffer.from_strips_and_edge(
            label_strips,
            edge=(u_buffer.node, v_buffer.node),
            z_index=1,
            shape=shape,
            center=label_position,
        )
        label_buffers.append(label_buffer)

    label_buffers.extend(
        render_arrow_tip_buffers(
            (u_buffer.node, v_buffer.node),
            properties.end_arrow_tip,
            properties.start_arrow_tip,
            edge_segments,
            properties.segment_drawing_mode,
            style=properties.style,
        )
    )

    boundary_1 = edge_segments.min_bound
    boundary_2 = edge_segments.max_bound

    if boundary_1 == boundary_2:
        return None

    edge_buffer = EdgeBuffer(
        edge=(u_buffer.node, v_buffer.node),
        z_index=edge_layout.z_index,
        boundary_1=boundary_1,
        boundary_2=boundary_2,
        strips=strips,
    )

    return edge_buffer, edge_layout, label_buffers
