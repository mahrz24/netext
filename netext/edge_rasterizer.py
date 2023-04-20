from typing import Any

from rich.console import Console
from rich.style import Style
from netext.edge_rendering.arrow_tips import render_arrow_tip_buffers
from netext.edge_rendering.bitmap import bitmap_to_strips
from netext.edge_rendering.box import orthogonal_segments_to_strips_with_box_characters
from netext.edge_rendering.bresenham import rasterize_edge_segments
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.edge import EdgeLayout
from netext.edge_routing.edge import EdgeInput
from netext.edge_routing.route import route_edge
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Magnet

from netext.node_rasterizer import JustContent, NodeBuffer
from netext.rendering.segment_buffer import StripBuffer
from rtree.index import Index

# label_position: Point | None
# start_tip_position: Point | None
# end_tip_position: Point | None


def rasterize_edge(
    console: Console,
    u_buffer: NodeBuffer,
    v_buffer: NodeBuffer,
    all_nodes: list[NodeBuffer],
    routed_edges: list[EdgeLayout],
    data: Any,
    node_idx: Index,
    edge_idx: Index,
) -> tuple[EdgeBuffer, EdgeLayout, list[StripBuffer]] | None:
    show = data.get("$show", True)

    if not show:
        return None

    start = u_buffer.get_magnet_position(
        v_buffer.center, data.get("$magnet", Magnet.CENTER)
    )

    end = v_buffer.get_magnet_position(
        u_buffer.center, data.get("$magnet", Magnet.CENTER)
    )

    end_arrow_tip = data.get("$end-arrow-tip", None)
    start_arrow_tip = data.get("$start-arrow-tip", None)

    routing_mode: EdgeRoutingMode = data.get(
        "$edge-routing-mode", EdgeRoutingMode.straight
    )
    edge_segment_drawing_mode: EdgeSegmentDrawingMode = data.get(
        "$edge-segment-drawing-mode", EdgeSegmentDrawingMode.single_character
    )

    edge_input = EdgeInput(
        start=start,
        end=end,
        routing_mode=routing_mode,
        edge_segment_drawing_mode=edge_segment_drawing_mode,
        routing_hints=[],
    )

    # We perform a two pass routing here.

    # First we route the edge with allowing the center magnet as start and end
    # This routing already tries to avoid other nodes.
    non_start_end_node_indices = [
        i
        for i, node_buffer in enumerate(all_nodes)
        if node_buffer is not u_buffer and node_buffer is not v_buffer
    ]

    routed_edge_indices = range(len(routed_edges))

    edge_segments = route_edge(
        start,
        end,
        routing_mode,
        all_nodes,
        routed_edges,
        non_start_end_node_indices,
        routed_edge_indices,
        node_idx,
        edge_idx,
    )

    # Then we cut the edge with the node boundaries.

    edge_segments = edge_segments.cut_with_nodes([u_buffer, v_buffer])

    if not edge_segments.segments:
        return None

    if edge_segment_drawing_mode == EdgeSegmentDrawingMode.box:
        assert (
            routing_mode == EdgeRoutingMode.orthogonal
        ), "Box characters are only supported on orthogonal lines"
        strips = orthogonal_segments_to_strips_with_box_characters(
            edge_segments.segments
        )
    else:
        # In case of pixel / braille we scale and then map character per character
        match edge_segment_drawing_mode:
            case EdgeSegmentDrawingMode.single_character:
                x_scaling = 1
                y_scaling = 1
            case EdgeSegmentDrawingMode.braille:
                x_scaling = 2
                y_scaling = 4
            case EdgeSegmentDrawingMode.block:
                x_scaling = 2
                y_scaling = 2

        bitmap_buffer = rasterize_edge_segments(
            edge_segments.segments, x_scaling=x_scaling, y_scaling=y_scaling
        )
        strips = bitmap_to_strips(
            bitmap_buffer, edge_segment_drawing_mode=edge_segment_drawing_mode
        )

    edge_layout = EdgeLayout(input=edge_input, segments=edge_segments.segments)

    label_buffers: list[StripBuffer] = []
    label = data.get("$label", None)

    # TODO Think about this: Shape and node buffer are bound
    # so maybe use the shape to create the node buffer
    # and link it to the creating shape?
    if label is not None:
        shape = JustContent()
        label_strips = shape.render_shape(console, label, style=Style(), data={})

        label_position = edge_segments.edge_iter_point(round(edge_segments.length / 2))

        label_buffer = NodeBuffer.from_strips(
            label_strips, z_index=1, shape=shape, center=label_position
        )
        label_buffers.append(label_buffer)

    label_buffers.extend(
        render_arrow_tip_buffers(
            end_arrow_tip, start_arrow_tip, edge_segments, edge_segment_drawing_mode
        )
    )

    boundary_1 = edge_segments.min_bound
    boundary_2 = edge_segments.max_bound

    edge_buffer = EdgeBuffer(
        z_index=0,
        boundary_1=boundary_1,
        boundary_2=boundary_2,
        strips=strips,
    )

    return edge_buffer, edge_layout, label_buffers
