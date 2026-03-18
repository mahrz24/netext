"""Helper functions for ConsoleGraph CRUD mutation methods.

These extract repeated patterns from add_node, update_node, etc.
ConsoleGraph remains the state owner and orchestrates calls.
"""

from collections.abc import Hashable
from typing import Any, cast

from rich.console import Console

import netext._core as core
from netext._core import Point
from netext.edge_rasterizer import rasterize_edge
from netext.edge_rendering.buffer import EdgeBuffer
from netext.geometry.point import FloatPoint
from netext.graph_transitions import register_edge_with_router
from netext.node_rasterizer import NodeBuffer, rasterize_node
from netext.properties.edge import EdgeProperties
from netext.properties.node import NodeProperties
from netext.rendering.segment_buffer import StripBuffer


def compute_node_view_position(position: FloatPoint, zoom_x: float, zoom_y: float) -> Point:
    """Convert a node position from graph space to view space."""
    return Point(round(position.x * zoom_x), round(position.y * zoom_y))


def rasterize_node_for_layout(
    console: Console,
    node: Hashable,
    data: dict[str, Any],
    layout_direction: core.LayoutDirection,
) -> NodeBuffer:
    """Rasterize a node at default LOD for layout purposes and determine edge sides."""
    node_buffer = rasterize_node(console, node, cast(dict[str, Any], data))
    node_buffer.determine_edge_sides(layout_direction=layout_direction)
    return node_buffer


def rasterize_node_at_lod(
    console: Console,
    node: Hashable,
    data: dict[str, Any],
    zoom_factor: float | None,
    node_anchors: Any,
    lod: int | None = None,
) -> NodeBuffer:
    """Rasterize a node at the appropriate LOD for display.

    If lod is not provided, it is computed from the zoom_factor and node properties.
    """
    if lod is None:
        properties = NodeProperties.from_data_dict(data)
        lod = properties.lod_map(zoom_factor) if zoom_factor is not None else 1

    node_buffer = rasterize_node(
        console,
        node,
        data,
        lod=lod,
        node_anchors=node_anchors,
    )
    return node_buffer


def check_zoom_recomputation(
    zoom_spec: Any,
    current_zoom_factor: float | None,
    compute_zoom_fn: Any,
) -> tuple[bool, float]:
    """Check if zoom needs recomputation (e.g. for AutoZoom modes).

    Returns (needs_full_recompute, new_zoom_factor).
    """
    from netext.console_graph import AutoZoom

    zoom_factor = current_zoom_factor if current_zoom_factor is not None else 0
    if zoom_spec is AutoZoom.FIT or zoom_spec is AutoZoom.FIT_PROPORTIONAL or current_zoom_factor is None:
        zoom_x, zoom_y = compute_zoom_fn()
        zoom_factor = min([zoom_x, zoom_y])

    return zoom_factor != current_zoom_factor, zoom_factor


def rasterize_and_store_edge(
    console: Console,
    core_graph: core.CoreGraph,
    u: Hashable,
    v: Hashable,
    node_buffers: dict[Hashable, NodeBuffer],
    edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer],
    edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]],
    properties: EdgeProperties,
    zoom_factor: float,
    edge_index: int,
    layout_direction: core.LayoutDirection,
) -> None:
    """Rasterize an edge and store the results in edge_buffers/edge_label_buffers."""
    edge_lod = properties.lod_map(zoom_factor)

    result = rasterize_edge(
        console,
        core_graph,
        node_buffers[u],
        node_buffers[v],
        properties,
        edge_lod,
        edge_index=edge_index,
        layout_direction=layout_direction,
    )

    edge_buffer: EdgeBuffer | None = None
    label_nodes: list[StripBuffer] | None = None

    if result is not None:
        edge_buffer, label_nodes = result
    if edge_buffer is not None:
        edge_buffers[(u, v)] = edge_buffer
        register_edge_with_router(core_graph, u, v, edge_buffer)
    if label_nodes is not None:
        edge_label_buffers[(u, v)] = label_nodes


def remove_existing_edge_buffers(
    u: Hashable,
    v: Hashable,
    node_buffers: dict[Hashable, NodeBuffer],
    edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer],
    edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]],
) -> int:
    """Disconnect nodes, delete old buffers.

    Returns the old z_index for reuse.
    The router entry is cleaned up when the edge is re-registered via register_edge_with_router.
    """
    node_buffers[v].disconnect(u)
    node_buffers[u].disconnect(v)

    old_z_index = edge_buffers[(u, v)].z_index.layer_index

    del edge_buffers[(u, v)]
    del edge_label_buffers[(u, v)]

    return int(old_z_index)


def rerender_connected_edges(
    console: Console,
    core_graph: core.CoreGraph,
    node: Hashable,
    node_buffers: dict[Hashable, NodeBuffer],
    edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer],
    edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]],
    zoom_factor: float,
    layout_direction: core.LayoutDirection,
    port_buffers: dict[Hashable, list[StripBuffer]],
    render_port_fn: Any,
) -> None:
    """Find edges connected to a node and re-render them.

    Mutates edge_buffers, edge_label_buffers, and port_buffers in place.
    """
    affected_edges: list[tuple[Hashable, Hashable]] = []

    for v in core_graph.neighbors(node):
        if (node, v) in edge_buffers:
            affected_edges.append((node, v))
        if (v, node) in edge_buffers:
            affected_edges.append((v, node))

    for u, v in affected_edges:
        _rerender_single_edge(
            console, core_graph, u, v,
            node_buffers, edge_buffers, edge_label_buffers,
            zoom_factor, layout_direction,
        )
        render_port_fn(u)
        render_port_fn(v)


def _rerender_single_edge(
    console: Console,
    core_graph: core.CoreGraph,
    u: Hashable,
    v: Hashable,
    node_buffers: dict[Hashable, NodeBuffer],
    edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer],
    edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]],
    zoom_factor: float,
    layout_direction: core.LayoutDirection,
) -> None:
    """Re-render a single edge (used during node mutation)."""
    old_data = core_graph.edge_data(u, v)
    data = dict(old_data)
    if "$properties" in data:
        del data["$properties"]

    properties = EdgeProperties.from_data_dict(data)
    core_graph.update_edge_data(u, v, dict(data, **{"$properties": properties}))

    old_z_index = remove_existing_edge_buffers(
        u, v, node_buffers, edge_buffers, edge_label_buffers,
    )

    rasterize_and_store_edge(
        console, core_graph, u, v, node_buffers,
        edge_buffers, edge_label_buffers,
        properties, zoom_factor, old_z_index, layout_direction,
    )
