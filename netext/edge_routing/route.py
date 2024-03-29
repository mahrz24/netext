
import netext._core as core
from netext._core import Direction
from netext.edge_routing.edge import EdgeLayout, EdgePath
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer


def route_edge(
    start: Point,
    end: Point,
    all_nodes: list[NodeBuffer],
    routed_edges: list[EdgeLayout],
    start_helper: Point | None = None,
    end_helper: Point | None = None,
) -> EdgePath:
    helper_points: list[Point] = []
    if start_helper is not None:
        helper_points.append(start_helper)
    if end_helper is not None:
        helper_points.append(end_helper)

    # TODO Compute initial direction from helper
    start_direction = Direction.CENTER
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

    end_direction = Direction.CENTER
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

    path = core.route_edge(
        start=core.Point(x=start.x, y=start.y),
        end=core.Point(x=end.x, y=end.y),
        start_direction=start_direction,
        end_direction=end_direction,
        nodes=[],
        routed_edges=[],
    )

    return EdgePath(
        start=start,
        end=end,
        directed_points=[(Point(x=x, y=y), direction) for (x, y, direction) in path],
    )


def generate_edge_graph(left_x, right_x, top_y, bottom_y):
    all_directions = [
        Direction.CENTER,
        Direction.UP,
        Direction.DOWN,
        Direction.LEFT,
        Direction.RIGHT,
        Direction.UP_RIGHT,
        Direction.UP_LEFT,
        Direction.DOWN_RIGHT,
        Direction.DOWN_LEFT,
    ]

    all_positions = [(x, y) for x in range(left_x - 3, right_x + 4) for y in range(top_y - 3, bottom_y + 4)]
    edges = []
    nodes = [(x, y, dir) for (x, y) in all_positions for dir in all_directions]

    edges.append(
        (
            [
                ((x, y, Direction.DOWN), (x, y + 1, Direction.UP))
                for x in range(left_x - 3, right_x + 4)
                for y in range(top_y - 3, bottom_y + 3)
            ],
            1,
        )
    )

    edges.append(
        (
            [
                ((x, y, Direction.RIGHT), (x + 1, y, Direction.LEFT))
                for x in range(left_x - 3, right_x + 3)
                for y in range(top_y - 3, bottom_y + 4)
            ],
            1,
        )
    )

    edges.append(
        (
            [
                ((x, y, Direction.UP_RIGHT), (x + 1, y - 1, Direction.DOWN_LEFT))
                for x in range(left_x - 3, right_x + 3)
                for y in range(top_y - 2, bottom_y + 4)
            ],
            2,
        )
    )

    edges.append(
        (
            [
                ((x, y, Direction.DOWN_RIGHT), (x + 1, y + 1, Direction.UP_LEFT))
                for x in range(left_x - 3, right_x + 3)
                for y in range(top_y - 3, bottom_y + 4)
            ],
            2,
        )
    )

    for src in all_directions:
        for tgt in all_directions:
            if src != tgt:
                weight = 2
                if (src, tgt) in [
                    (Direction.UP, Direction.DOWN),
                    (Direction.DOWN, Direction.UP),
                    (Direction.LEFT, Direction.RIGHT),
                    (Direction.RIGHT, Direction.LEFT),
                ]:
                    weight = 1
                edges.append(
                    (
                        [((x, y, src), (x, y, tgt)) for (x, y) in all_positions],
                        weight,
                    )
                )

    return nodes, edges
