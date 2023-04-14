from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer


from typing import Iterable


def route_orthogonal_edge(
    start: Point,
    end: Point,
    non_start_end_nodes: Iterable[NodeBuffer],
    routed_edges: Iterable[EdgeLayout] = [],
    recursion_depth: int = 0,
) -> RoutedEdgeSegments:
    """
    Route an edge from start to end using orthogonal segments.
    The edge will be routed in a way that minimizes the number of intersections with other nodes.
    """
    # TODO: Add different midpoints as candidates.
    candidates = [
        RoutedEdgeSegments.from_segments_compute_intersections(
            EdgeSegment(start=start, end=end).ortho_split_x(),
            node_buffers=non_start_end_nodes,
            edges=routed_edges,
        ),
        RoutedEdgeSegments.from_segments_compute_intersections(
            EdgeSegment(start=start, end=end).ortho_split_y(),
            node_buffers=non_start_end_nodes,
            edges=routed_edges,
        ),
    ]

    if (
        all([candidate.intersections > 0 for candidate in candidates])
        and start.distance_to(end) >= 4
        and recursion_depth < 2
    ):
        candidates.append(
            route_orthogonal_edge(
                start=start,
                end=EdgeSegment(start=start, end=end).midpoint,
                non_start_end_nodes=non_start_end_nodes,
                routed_edges=routed_edges,
                recursion_depth=recursion_depth + 1,
            ).concat(
                route_orthogonal_edge(
                    start=EdgeSegment(start=start, end=end).midpoint,
                    end=end,
                    non_start_end_nodes=non_start_end_nodes,
                    routed_edges=routed_edges,
                    recursion_depth=recursion_depth + 1,
                )
            )
        )

    return min(candidates, key=lambda candidate: candidate.intersections)
