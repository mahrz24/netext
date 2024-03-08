from typing import cast
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import Direction, EdgeLayout, EdgePath, EdgeSegment, RoutedEdgeSegments
from netext.geometry import Point
from netext.geometry.index import BufferIndex
from netext.node_rasterizer import NodeBuffer
import networkx as nx


def route_edge(
    start: Point,
    end: Point,
    all_nodes: list[NodeBuffer] = [],
    routed_edges: list[EdgeLayout] = [],
    node_idx: BufferIndex[NodeBuffer, None] | None = None,
    edge_idx: BufferIndex[EdgeBuffer, EdgeLayout] | None = None,
    recursion_depth: int = 0,
    start_helper: Point | None = None,
    end_helper: Point | None = None,
) -> EdgePath:
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

    # Generate a graph from spaning all nodes and edges and some additional space to avoid intersections the graph has four
    # nodes per coordinate to generate a grid of nodes where the needed character can be routed.

    # This is a naive but correct implementation of the graph generation. It is not optimized and can be improved.
    # The nice thing about this implementation is that it is very easy to understand and debug and also powerful in terms
    # of routing. It can be used to route any kind of edge, not only orthogonal edges. With modifications to the weights
    # we can control a lot of the routing behavior.

    G = nx.Graph()

    all_directions = [
        Direction.UP,
        Direction.DOWN,
        Direction.LEFT,
        Direction.RIGHT,
        Direction.UP_RIGHT,
        Direction.UP_LEFT,
        Direction.DOWN_RIGHT,
        Direction.DOWN_LEFT,
    ]

    G.add_nodes_from(
        [
            (x, y, dir)
            for x in range(left_x - 3, right_x + 11)
            for y in range(top_y - 3, bottom_y + 11)
            for dir in all_directions
        ]
    )

    G.add_edges_from(
        [
            ((x, y, Direction.DOWN), (x, y + 1, Direction.UP))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 3)
        ],
        **{"weight": 1},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.RIGHT), (x + 1, y, Direction.LEFT))
            for x in range(left_x - 3, right_x + 3)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 1},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.UP_RIGHT), (x + 1, y - 1, Direction.DOWN_LEFT))
            for x in range(left_x - 3, right_x + 3)
            for y in range(top_y - 2, bottom_y + 4)
        ],
        **{"weight": 1},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.DOWN_RIGHT), (x + 1, y + 1, Direction.UP_LEFT))
            for x in range(left_x - 3, right_x + 3)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 1},
    )

    # Add edges for changing direction (the graph is not directed)
    G.add_edges_from(
        [
            ((x, y, Direction.UP), (x, y, Direction.DOWN))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 0},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.LEFT), (x, y, Direction.RIGHT))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 0},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.LEFT), (x, y, Direction.UP))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 0},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.LEFT), (x, y, Direction.DOWN))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 0},
    )

    G.add_edges_from(
        [
            ((x, y, Direction.UP), (x, y, Direction.RIGHT))
            for x in range(left_x - 3, right_x + 4)
            for y in range(top_y - 3, bottom_y + 4)
        ],
        **{"weight": 0},
    )

    for src in all_directions:
        for tgt in all_directions:
            if src != tgt:
                G.add_edges_from(
                    [
                        ((x, y, src), (x, y, tgt))
                        for x in range(left_x - 3, right_x + 4)
                        for y in range(top_y - 3, bottom_y + 4)
                    ],
                    **{"weight": 0},
                )

    # Remove weights for edges covered by nodes
    for node in all_nodes:
        for x in range(node.left_x, node.right_x + 1):
            for y in range(node.top_y, node.bottom_y + 1):
                edges = list(nx.edges(G, (x, y, Direction.UP)))
                edges += list(nx.edges(G, (x, y, Direction.DOWN)))
                edges += list(nx.edges(G, (x, y, Direction.LEFT)))
                edges += list(nx.edges(G, (x, y, Direction.RIGHT)))
                for edge in edges:
                    G.edges[edge]["weight"] = None

    # TODO Compute initial direction from helper
    start_direction = Direction.UP
    if start_helper is not None:
        delta = start_helper - start
        if delta.x > 0 and delta.y > 0:
            start_direction = Direction.UP_RIGHT
        elif delta.x > 0 and delta.y < 0:
            start_direction = Direction.DOWN_RIGHT
        elif delta.x < 0 and delta.y > 0:
            start_direction = Direction.UP_LEFT
        elif delta.x < 0 and delta.y < 0:
            start_direction = Direction.DOWN_LEFT
        elif delta.x > 0:
            start_direction = Direction.RIGHT
        elif delta.x < 0:
            start_direction = Direction.LEFT
        elif delta.y > 0:
            start_direction = Direction.UP
        else:
            start_direction = Direction.DOWN

    end_direction = Direction.UP
    if end_helper is not None:
        delta = end_helper - end
        if delta.x > 0 and delta.y > 0:
            end_direction = Direction.UP_RIGHT
        elif delta.x > 0 and delta.y < 0:
            end_direction = Direction.DOWN_RIGHT
        elif delta.x < 0 and delta.y > 0:
            end_direction = Direction.UP_LEFT
        elif delta.x < 0 and delta.y < 0:
            end_direction = Direction.DOWN_LEFT
        elif delta.x > 0:
            end_direction = Direction.RIGHT
        elif delta.x < 0:
            end_direction = Direction.LEFT
        elif delta.y > 0:
            end_direction = Direction.UP
        else:
            end_direction = Direction.DOWN

    path = cast(
        list[tuple[int, int, Direction]],
        nx.shortest_paths.dijkstra_path(G, (start.x, start.y, start_direction), (end.x, end.y, end_direction)),
    )

    return EdgePath(
        start=start,
        end=end,
        points=[
            (Point(x=x, y=y), direction)
            for (x, y, direction) in path
            if (x, y, direction) != (start.x, start.y, Direction.UP)
            and (x, y, direction) != (end.x, end.y, Direction.UP)
        ],
    )
