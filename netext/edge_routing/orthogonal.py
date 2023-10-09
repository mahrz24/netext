from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgeLayout, EdgeSegment, RoutedEdgeSegments
from netext.geometry import Point
from netext.geometry.index import BufferIndex
from netext.geometry.line_segment import LineSegment
from netext.node_rasterizer import NodeBuffer
from shapely import LineString


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
    """
    Route an edge from start to end using orthogonal segments.
    The edge will be routed in a way that minimizes the number of intersections with other nodes.
    """
    straight_connection = LineSegment(start=start, end=end)
    relevant_nodes = all_nodes
    if node_idx is not None:
        relevant_nodes = node_idx.intersection(
            straight_connection.bounding_box, restrict=relevant_nodes
        )

    relevant_edges = routed_edges
    if edge_idx is not None:
        relevant_edges = edge_idx.annotations_for_intersection(
            straight_connection.bounding_box, restrict=relevant_edges
        )

    # If the start or endpoint are inside a node and recursion depth is 0
    # we route around it.

    helper_segments_start = []
    helper_segments_end = []

    if recursion_depth == 0:
        node_containing_start = next(
            (
                node
                for node in relevant_nodes
                if node.shape.polygon(node).covers(start.shapely)
            ),
            None,
        )

        if node_containing_start is not None and start_helper is not None:
            helper_point = start_helper
            helper_segments_start = [EdgeSegment(start=start, end=helper_point)]

            def _intersects_to_end(point: Point):
                direct_line_to_end = LineString([point.shapely, end.shapely])
                return node_containing_start.shape.polygon(
                    node_containing_start
                ).intersects(direct_line_to_end)

            if _intersects_to_end(helper_point):
                # We need to route around the node as our extrusion would still intersect it.
                helper_start = helper_point
                last_helper_segment = helper_segments_start[-1].shapely
                helper_point = Point.from_shapely(
                    last_helper_segment.offset_curve(
                        distance=last_helper_segment.length / 1.5
                    ).boundary.geoms[1]
                )

                # Our choice of direction might have been wrong, so we check again.
                # And if it is still wrong, we flip the direction.
                if _intersects_to_end(helper_point):
                    helper_point = Point.from_shapely(
                        last_helper_segment.offset_curve(
                            distance=-last_helper_segment.length / 1.5
                        ).boundary.geoms[1]
                    )

                helper_segments_start.append(
                    EdgeSegment(start=helper_start, end=helper_point)
                )
            start = helper_point

            node_containing_start = next(
                (
                    node
                    for node in relevant_nodes
                    if node.shape.polygon(node).covers(start.shapely)
                ),
                None,
            )

        node_containing_end = next(
            (
                node
                for node in relevant_nodes
                if node.shape.polygon(node).covers(end.shapely)
            ),
            None,
        )

        if node_containing_end is not None and end_helper is not None:
            helper_point = end_helper
            helper_segments_end = [EdgeSegment(start=helper_point, end=end)]

            def _intersects_to_end(point: Point):
                direct_line_to_end = LineString([start.shapely, point.shapely])
                return node_containing_end.shape.polygon(
                    node_containing_end
                ).intersects(direct_line_to_end)

            if _intersects_to_end(helper_point):
                # We need to route around the node as our extrusion would still intersect it.
                helper_end = helper_point
                last_helper_segment = helper_segments_end[-1].shapely
                helper_point = Point.from_shapely(
                    last_helper_segment.offset_curve(
                        distance=-last_helper_segment.length
                    ).boundary.geoms[0]
                )

                # Our choice of direction might have been wrong, so we check again.
                # And if it is still wrong, we flip the direction.
                if _intersects_to_end(helper_point):
                    helper_point = Point.from_shapely(
                        last_helper_segment.offset_curve(
                            distance=last_helper_segment.length
                        ).boundary.geoms[0]
                    )

                helper_segments_end.insert(
                    0, EdgeSegment(start=helper_point, end=helper_end)
                )
            end = helper_point

    candidates = [
        RoutedEdgeSegments.from_segments_compute_intersections(
            helper_segments_start
            + EdgeSegment(start=start, end=end).ortho_split_x()
            + helper_segments_end,
            node_buffers=relevant_nodes,
            edges=relevant_edges,
        ),
        RoutedEdgeSegments.from_segments_compute_intersections(
            helper_segments_start
            + EdgeSegment(start=start, end=end).ortho_split_y()
            + helper_segments_end,
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
            RoutedEdgeSegments(helper_segments_start, intersections=0)
            .concat(
                route_orthogonal_edge(
                    start=start,
                    end=EdgeSegment(start=start, end=end).midpoint,
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(
                route_orthogonal_edge(
                    start=EdgeSegment(start=start, end=end).midpoint,
                    end=end,
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(RoutedEdgeSegments(helper_segments_end, intersections=0))
        )

        candidates.append(
            RoutedEdgeSegments(helper_segments_start, intersections=0)
            .concat(
                route_orthogonal_edge(
                    start=start,
                    end=Point(start.x, round((end.y + start.y) / 2)),
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(
                route_orthogonal_edge(
                    start=Point(start.x, round((end.y + start.y) / 2)),
                    end=end,
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(RoutedEdgeSegments(helper_segments_end, intersections=0))
        )

        candidates.append(
            RoutedEdgeSegments(helper_segments_start, intersections=0)
            .concat(
                route_orthogonal_edge(
                    start=start,
                    end=Point(round((end.x + start.x) / 2), start.y),
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(
                route_orthogonal_edge(
                    start=Point(round((end.x + start.x) / 2), start.y),
                    end=end,
                    all_nodes=relevant_nodes,
                    routed_edges=relevant_edges,
                    node_idx=node_idx,
                    edge_idx=edge_idx,
                    recursion_depth=recursion_depth + 1,
                )
            )
            .concat(RoutedEdgeSegments(helper_segments_end, intersections=0))
        )

    return min(candidates, key=lambda candidate: candidate.intersections)
