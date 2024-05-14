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

    shapes = [
        core.Shape(
            top_left=core.Point(x=node.left_x, y=node.top_y), bottom_right=core.Point(x=node.right_x, y=node.bottom_y)
        )
        for node in all_nodes
    ]
    lines = [[core.Point(x=point[0].x, y=point[0].y) for point in edge.path.directed_points] for edge in routed_edges]

    hints = []

    if start.x != end.x and start.y != end.y:
        hints.append(core.Point(x=start.x, y=end.y))
        hints.append(core.Point(x=end.x, y=start.y))
        # hints.append(core.Point(x=(start.x + end.x) // 2, y=(start.y + end.y) // 2))

    path = core.route_edge(
        start=core.Point(x=start.x, y=start.y),
        end=core.Point(x=end.x, y=end.y),
        start_direction=start_direction,
        end_direction=end_direction,
        shapes=shapes,
        lines=lines,
        hints=hints,
        config=core.RoutingConfig(
            canvas_padding=5,
            subdivision_size=7,
            overlap=7,
            shape_margin=1,
            line_margin=1,
            neighborhood=core.Neighborhood.MOORE,
            corner_cost=2,
            diagonal_cost=100,
            line_cost=10,
            shape_cost=10,
            hint_cost=0,
        ),
    )

    return EdgePath(
        start=start,
        end=end,
        directed_points=[(Point(x=x, y=y), direction) for (x, y, direction) in path],
    )
