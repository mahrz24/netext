from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_routing.orthogonal import route_orthogonal_edge
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer


from rtree.index import Index


def route_edge(
    start: Point,
    end: Point,
    routing_mode: EdgeRoutingMode,
    all_nodes: list[NodeBuffer] = [],
    routed_edges: list[EdgeLayout] = [],
    node_view: list[int] = [],
    edge_view: list[int] = [],
    node_idx: Index | None = None,
    edge_idx: Index | None = None,
) -> RoutedEdgeSegments:
    match routing_mode:
        case EdgeRoutingMode.STRAIGHT:
            # We don't need to check for intersections here, because the edge is straight.
            return RoutedEdgeSegments(
                segments=[EdgeSegment(start=start, end=end)], intersections=0
            )
        case EdgeRoutingMode.ORTHOGONAL:
            return route_orthogonal_edge(
                start=start,
                end=end,
                all_nodes=all_nodes,
                routed_edges=routed_edges,
                node_view=node_view,
                edge_view=edge_view,
                node_idx=node_idx,
                edge_idx=edge_idx,
            )
        case _:
            raise NotImplementedError(
                f"The routing mode {routing_mode} has not been implemented yet."
            )
