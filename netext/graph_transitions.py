"""Standalone functions for ConsoleGraph state transitions.

These are pure(ish) computational functions extracted from ConsoleGraph's
transition methods. ConsoleGraph remains the state owner and calls these
functions, storing the results.
"""

from collections.abc import Hashable
from typing import Any, cast

import statistics

from rich.console import Console

import netext._core as core
from netext._core import Point
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_rasterizer import EdgeRoutingRequest, rasterize_edges
from netext.geometry.point import FloatPoint
from netext.node_rasterizer import NodeBuffer, rasterize_node
from netext.properties.edge import EdgeProperties
from netext.properties.node import NodeProperties
from netext.rendering.segment_buffer import StripBuffer


def render_node_buffers_for_layout(
    console: Console,
    core_graph: core.CoreGraph,
) -> dict[Hashable, NodeBuffer]:
    """Rasterize all nodes at default LOD for layout sizing.

    Also updates core_graph node sizes as a side effect.
    """
    node_buffers = {
        node: rasterize_node(
            console, node, cast(dict[str, Any], core_graph.node_data_or_default(node, dict()))
        )
        for node in core_graph.all_nodes()
    }
    for node in core_graph.all_nodes():
        core_graph.update_node_size(
            node,
            core.Size(
                node_buffers[node].layout_width + 10,
                node_buffers[node].layout_height + 5,
            ),
        )
    return node_buffers


def compute_node_layout(
    layout_engine: core.LayoutEngine,
    core_graph: core.CoreGraph,
    node_buffers_for_layout: dict[Hashable, NodeBuffer],
) -> FloatPoint:
    """Run the layout engine, store positions in core_graph, compute routing hints.

    Returns the offset used to center the layout.
    """
    node_positions = dict(
        [(n, FloatPoint(p.x, p.y)) for (n, p) in layout_engine.layout(core_graph)]
    )

    offset = FloatPoint(0, 0)

    if node_positions:
        x_positions = [pos.x for pos in node_positions.values()]
        y_positions = [pos.y for pos in node_positions.values()]
        min_x = min(x_positions)
        max_x = max(x_positions)
        min_y = min(y_positions)
        max_y = max(y_positions)

        offset = FloatPoint(-min_x - (max_x - min_x) / 2 + 0.25, -min_y - (max_y - min_y) / 2 + 0.25)

        node_positions = {node: pos + offset for node, pos in node_positions.items()}

        median_x = statistics.median(x_positions)
        median_y = statistics.median(y_positions)

        x_span = max_x - min_x
        y_span = max_y - min_y

        for node, position in node_positions.items():
            core_graph.set_node_position(node, position.x, position.y)
            node_buffers_for_layout[node].center = Point(x=round(position.x), y=round(position.y))
            node_buffers_for_layout[node].routing_hints.relative_offset_in_layout_direction = (
                ((position.x - median_x) / x_span if x_span else 0.0)
                if layout_engine.layout_direction == core.LayoutDirection.LEFT_RIGHT
                else ((position.y - median_y) / y_span if y_span else 0.0)
            )

        _compute_layout_density(node_buffers_for_layout, layout_engine.layout_direction)

    _compute_port_sides(layout_engine, core_graph, node_buffers_for_layout)

    return offset


def _compute_layout_density(
    node_buffers_for_layout: dict[Hashable, NodeBuffer],
    layout_direction: core.LayoutDirection,
) -> None:
    """Compute density of nodes in the layout direction for routing hints."""
    for node, node_buffer in node_buffers_for_layout.items():
        if layout_direction == core.LayoutDirection.LEFT_RIGHT:
            row_min = node_buffer.center.y - node_buffer.layout_height / 2
            row_max = node_buffer.center.y + node_buffer.layout_height / 2
            density = sum(
                1
                for other in node_buffers_for_layout.values()
                if (
                    other.center.y + other.layout_height / 2 >= row_min
                    and other.center.y - other.layout_height / 2 <= row_max
                )
            )
        else:
            col_min = node_buffer.center.x - node_buffer.layout_width / 2
            col_max = node_buffer.center.x + node_buffer.layout_width / 2
            density = sum(
                1
                for other in node_buffers_for_layout.values()
                if (
                    other.center.x + other.layout_width / 2 >= col_min
                    and other.center.x - other.layout_width / 2 <= col_max
                )
            )
        node_buffer.routing_hints.density_in_layout_direction = density


def _compute_port_sides(
    layout_engine: core.LayoutEngine,
    core_graph: core.CoreGraph,
    node_buffers_for_layout: dict[Hashable, NodeBuffer],
) -> None:
    """Compute the port sides for each node based on neighbor positions."""
    for node, node_buffer in node_buffers_for_layout.items():
        out_neighbors = [
            (
                node_buffers_for_layout[other],
                EdgeProperties.from_data_dict(core_graph.edge_data_or_default(node, other, dict())),
            )
            for other in core_graph.neighbors_outgoing(node)
        ]
        in_neighbors = [
            (
                node_buffers_for_layout[other],
                EdgeProperties.from_data_dict(core_graph.edge_data_or_default(other, node, dict())),
            )
            for other in core_graph.neighbors_incoming(node)
        ]

        node_buffer.determine_edge_sides(
            out_neighbors=out_neighbors,
            in_neighbors=in_neighbors,
            layout_direction=layout_engine.layout_direction,
        )


def compute_zoom(
    zoom_spec: Any,  # ZoomSpec | AutoZoom
    core_graph: core.CoreGraph,
    node_buffers_for_layout: dict[Hashable, NodeBuffer],
    max_width: int | None,
    max_height: int | None,
) -> tuple[float, float]:
    """Compute zoom_x and zoom_y from the zoom specification and current layout.

    The caller imports AutoZoom and ZoomSpec; we use duck typing / isinstance checks
    via the passed-in zoom_spec.
    """
    from netext.console_graph import AutoZoom, ZoomSpec

    all_positions = core_graph.all_node_positions()
    if all_positions:
        x_values = [x for _, (x, _) in all_positions]
        y_values = [y for _, (_, y) in all_positions]
        max_node_x = max(x_values)
        max_node_y = max(y_values)
        min_node_x = min(x_values)
        min_node_y = min(y_values)

        max_buffer_width = max([buffer.width for buffer in node_buffers_for_layout.values()])
        max_buffer_height = max([buffer.height for buffer in node_buffers_for_layout.values()])

        width = (max_node_x - min_node_x) + max_buffer_width + 2
        height = (max_node_y - min_node_y) + max_buffer_height + 2

        match zoom_spec:
            case AutoZoom.FIT:
                if max_width is None or max_height is None:
                    raise ValueError(
                        "AutoZoom.FIT is onlye allowed if the maximum renderable width and height is known."
                    )
                zoom_x = max_width / width
                zoom_y = max_height / height
            case AutoZoom.FIT_PROPORTIONAL:
                if max_width is None or max_height is None:
                    raise ValueError(
                        "AutoZoom.FIT is only allowed if the maximum renderable width and height is known."
                    )
                zoom_x = max_width / width
                zoom_y = max_height / height
                zoom_y = zoom_x = min(zoom_x, zoom_y)
            case ZoomSpec(x, y):
                zoom_x = x
                zoom_y = y
            case _:
                raise ValueError(f"Invalid zoom value {zoom_spec}")
    else:
        zoom_x = 1
        zoom_y = 1
    return zoom_x, zoom_y


def render_node_buffers_at_zoom(
    console: Console,
    core_graph: core.CoreGraph,
    node_buffers_for_layout: dict[Hashable, NodeBuffer],
    zoom_x: float,
    zoom_y: float,
    zoom_factor: float,
) -> dict[Hashable, NodeBuffer]:
    """Rasterize all nodes at the current zoom/LOD and register with edge router."""
    node_buffers: dict[Hashable, NodeBuffer] = {}

    for node in core_graph.all_nodes():
        data = core_graph.node_data_or_default(node, dict())
        properties = NodeProperties.from_data_dict(data)
        lod = properties.lod_map(zoom_factor)
        pos_x, pos_y = core_graph.get_node_position(node)
        position_view_space = Point(round(pos_x * zoom_x), round(pos_y * zoom_y))

        node_buffer = rasterize_node(
            console,
            node,
            data,
            lod=lod,
            node_anchors=node_buffers_for_layout[node].node_anchors,
        )

        node_buffer.center = position_view_space
        node_buffers[node] = node_buffer

        register_node_with_router(core_graph, node, node_buffer)

        node_buffer.determine_edge_positions()

    return node_buffers


def render_all_edges(
    console: Console,
    core_graph: core.CoreGraph,
    node_buffers: dict[Hashable, NodeBuffer],
    zoom_factor: float,
    layout_direction: core.LayoutDirection,
) -> tuple[
    dict[tuple[Hashable, Hashable], EdgeBuffer],
    dict[tuple[Hashable, Hashable], list[StripBuffer]],
]:
    """Rasterize all edges and register them with the embedded edge router.

    Returns (edge_buffers, edge_label_buffers).
    """
    edge_routing_requests = []

    for u, v in core_graph.all_edges():
        data = core_graph.edge_data_or_default(u, v, dict())
        properties = EdgeProperties.from_data_dict(data)
        edge_lod = properties.lod_map(zoom_factor)

        edge_routing_requests.append(
            EdgeRoutingRequest(
                u=u,
                v=v,
                u_buffer=node_buffers[u],
                v_buffer=node_buffers[v],
                properties=properties,
                lod=edge_lod,
            )
        )

    edge_buffers_result, label_buffers_result = rasterize_edges(
        console,
        core_graph,
        edge_routing_requests,
        layout_direction=layout_direction,
    )

    edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer] = {}
    edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]] = {}

    for (u, v), edge_buffer in edge_buffers_result.items():
        edge_buffers[(u, v)] = edge_buffer
        register_edge_with_router(core_graph, u, v, edge_buffer)

    for (u, v), label_nodes in label_buffers_result.items():
        edge_label_buffers[(u, v)] = label_nodes

    return edge_buffers, edge_label_buffers


def register_node_with_router(
    core_graph: core.CoreGraph,
    node: Hashable,
    node_buffer: NodeBuffer,
) -> None:
    """Register (or update) a node's bounding box with the embedded edge router."""
    placed_node = core.PlacedRectangularNode(
        center=core.Point(node_buffer.center.x, node_buffer.center.y),
        node=core.RectangularNode(
            size=core.Size(node_buffer.width, node_buffer.height),
        ),
    )
    core_graph.router_update_node(node, placed_node)


def register_edge_with_router(
    core_graph: core.CoreGraph,
    u: Hashable,
    v: Hashable,
    edge_buffer: EdgeBuffer,
) -> None:
    """Register (or update) an edge's path with the embedded edge router."""
    if edge_buffer.path is None:
        return
    line = [directed_point.point for directed_point in edge_buffer.path.directed_points]
    core_graph.router_update_edge(u, v, line)
