from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.geometry import Point
from netext.geometry.line_segment import LineSegment
from netext.node_rasterizer import NodeBuffer


from rtree.index import Index


def route_orthogonal_edge(
    start: Point,
    end: Point,
    all_nodes: list[NodeBuffer] = [],
    routed_edges: list[EdgeLayout] = [],
    node_view: list[int] = [],
    edge_view: list[int] = [],
    node_idx: Index | None = None,
    edge_idx: Index | None = None,
    recursion_depth: int = 0,
) -> RoutedEdgeSegments:
    """
    Route an edge from start to end using orthogonal segments.
    The edge will be routed in a way that minimizes the number of intersections with other nodes.
    """
    straight_connection = LineSegment(start=start, end=end)

    node_candidates = None
    if node_idx is not None:
        node_candidates = list(
            node_idx.intersection(straight_connection.bounding_box, objects=False)
        )

    edge_candidates = None
    if edge_idx is not None:
        edge_candidates = list(
            edge_idx.intersection(straight_connection.bounding_box, objects=False)
        )

    relevant_nodes = [
        node
        for i, node in enumerate(all_nodes)
        if i in node_view and (node_candidates is None or i in node_candidates)
    ]

    relevant_edges = [
        edge
        for i, edge in enumerate(routed_edges)
        if i in edge_view and (edge_candidates is None or i in edge_candidates)
    ]

    # TODO: Add different midpoints as candidates.
    candidates = [
        RoutedEdgeSegments.from_segments_compute_intersections(
            EdgeSegment(start=start, end=end).ortho_split_x(),
            node_buffers=relevant_nodes,
            edges=relevant_edges,
        ),
        RoutedEdgeSegments.from_segments_compute_intersections(
            EdgeSegment(start=start, end=end).ortho_split_y(),
            node_buffers=relevant_nodes,
            edges=relevant_edges,
        ),
    ]

    if (
        all([candidate.intersections > 0 for candidate in candidates])
        and start.distance_to(end) >= 4
        and recursion_depth <= 2
    ):
        candidates.append(
            route_orthogonal_edge(
                start=start,
                end=EdgeSegment(start=start, end=end).midpoint,
                all_nodes=all_nodes,
                routed_edges=routed_edges,
                node_view=node_view,
                edge_view=edge_view,
                node_idx=node_idx,
                edge_idx=edge_idx,
                recursion_depth=recursion_depth + 1,
            ).concat(
                route_orthogonal_edge(
                    start=EdgeSegment(start=start, end=end).midpoint,
                    end=end,
                    all_nodes=all_nodes,
                    routed_edges=routed_edges,
                    node_view=node_view,
                    edge_view=edge_view,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
        )

        candidates.append(
            route_orthogonal_edge(
                start=start,
                end=Point(start.x, round((end.y + start.y) / 2)),
                all_nodes=all_nodes,
                routed_edges=routed_edges,
                node_view=node_view,
                edge_view=edge_view,
                node_idx=node_idx,
                edge_idx=edge_idx,
                recursion_depth=recursion_depth + 1,
            ).concat(
                route_orthogonal_edge(
                    start=Point(start.x, round((end.y + start.y) / 2)),
                    end=end,
                    all_nodes=all_nodes,
                    routed_edges=routed_edges,
                    node_view=node_view,
                    edge_view=edge_view,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
        )

        candidates.append(
            route_orthogonal_edge(
                start=start,
                end=Point(round((end.x + start.x) / 2), start.y),
                all_nodes=all_nodes,
                routed_edges=routed_edges,
                node_view=node_view,
                edge_view=edge_view,
                node_idx=node_idx,
                edge_idx=edge_idx,
                recursion_depth=recursion_depth + 1,
            ).concat(
                route_orthogonal_edge(
                    start=Point(round((end.x + start.x) / 2), start.y),
                    end=end,
                    all_nodes=all_nodes,
                    routed_edges=routed_edges,
                    node_view=node_view,
                    edge_view=edge_view,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
        )

    return min(candidates, key=lambda candidate: candidate.intersections)
