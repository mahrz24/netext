import netext._core as core
from netext._core import Direction
from netext.edge_routing.edge import EdgePath
from netext.geometry import Point

def route_edge(
    start: Point,
    end: Point,
    edge_router: core.EdgeRouter,
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

    path = edge_router.route_edge(
        start=core.Point(x=start.x, y=start.y),
        end=core.Point(x=end.x, y=end.y),
        start_direction=start_direction,
        end_direction=end_direction,
        config=core.RoutingConfig(
            neighborhood=core.Neighborhood.ORTHOGONAL,
            corner_cost=1,
            diagonal_cost=0,
            line_cost=10,
            shape_cost=2,
            shape_distance_cost=0,
            line_distance_cost=0
        ),
    )

    return EdgePath(
        start=start,
        end=end,
        directed_points=[(Point(x=x, y=y), direction) for (x, y, direction) in path],
    )
