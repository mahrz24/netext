from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.geometry import Point
from netext.geometry.index import BufferIndex
from netext.node_rasterizer import NodeBuffer


def route_orthogonal_edge(
    start: Point,
    end: Point,
    all_nodes: list[NodeBuffer] = [],
    routed_edges: list[EdgeLayout] = [],
    node_idx: BufferIndex[NodeBuffer, None] | None = None,
    edge_idx: BufferIndex[EdgeBuffer, EdgeLayout] | None = None,
    recursion_depth: int = 0,
    start_helper: Point | None = None,
    end_helper: Point | None = None,
) -> RoutedEdgeSegments:
    helper_points: list[Point] = []
    if start_helper is not None:
        helper_points.append(start_helper)
    if end_helper is not None:
        helper_points.append(end_helper)
    # Get the offset and maximum dimension that needs to be supported by the edge.
    left_x = min(
        start.x,
        end.x,
        *map(lambda p: p.x, helper_points),
        *map(lambda n: n.left_x, all_nodes),
        *map(lambda e: e.left_x, routed_edges),
    )

    right_x = max(
        start.x,
        end.x,
        *map(lambda p: p.x, helper_points),
        *map(lambda n: n.left_x, all_nodes),
        *map(lambda e: e.left_x, routed_edges),
    )

    top_y = min(
        start.y,
        end.y,
        *map(lambda p: p.y, helper_points),
        *map(lambda n: n.top_y, all_nodes),
        *map(lambda e: e.top_y, routed_edges),
    )

    bottom_y = max(
        start.y,
        end.y,
        *map(lambda p: p.y, helper_points),
        *map(lambda n: n.bottom_y, all_nodes),
        *map(lambda e: e.bottom_y, routed_edges),
    )
    print(f"Possible routed dimensions {left_x=}, {right_x=}, {top_y=}, {bottom_y=}")
    return RoutedEdgeSegments(segments=[EdgeSegment(start=start, end=end)], intersections=0)
