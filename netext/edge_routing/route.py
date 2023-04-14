from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_routing.orthogonal import route_orthogonal_edge
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer


from typing import Iterable


def route_edge(
    start: Point,
    end: Point,
    routing_mode: EdgeRoutingMode,
    non_start_end_nodes: Iterable[NodeBuffer] = [],
    routed_edges: Iterable[EdgeLayout] = [],
) -> RoutedEdgeSegments:
    match routing_mode:
        case EdgeRoutingMode.straight:
            # We don't need to check for intersections here, because the edge is straight.
            return RoutedEdgeSegments(
                segments=[EdgeSegment(start=start, end=end)], intersections=0
            )
        case EdgeRoutingMode.orthogonal:
            return route_orthogonal_edge(
                start=start,
                end=end,
                non_start_end_nodes=non_start_end_nodes,
                routed_edges=routed_edges,
            )
        case _:
            raise NotImplementedError(
                f"The routing mode {routing_mode} has not been implemented yet."
            )
