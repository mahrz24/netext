import netext._core as core
from netext._core import Direction
from netext.edge_routing.edge import EdgePath
from netext.geometry import Point


def route_edge(
    start: Point,
    end: Point,
    start_direction: Direction,
    end_direction: Direction,
    edge_router: core.EdgeRouter,
) -> EdgePath:
    path = edge_router.route_edge(
        start=core.Point(x=start.x, y=start.y),
        end=core.Point(x=end.x, y=end.y),
        start_direction=start_direction,
        end_direction=end_direction,
        config=core.RoutingConfig(
            neighborhood=core.Neighborhood.MOORE,
            corner_cost=1,
            diagonal_cost=100,
            line_cost=10,
            shape_cost=5,
        ),
    )

    return EdgePath(
        start=start,
        end=end,
        directed_points=[(Point(x=x, y=y), direction) for (x, y, direction) in path],
    )


def route_edges(
    edge_router: core.EdgeRouter, edge_anchors: list[tuple[Point, Point, Direction, Direction]]
) -> list[EdgePath]:
    core_anchors = [
        (
            core.Point(x=start.x, y=start.y),
            core.Point(x=end.x, y=end.y),
            start_direction,
            end_direction,
            core.RoutingConfig(
                neighborhood=core.Neighborhood.MOORE,
                corner_cost=1,
                diagonal_cost=100,
                line_cost=10,
                shape_cost=5,
            ),
        )
        for start, end, start_direction, end_direction in edge_anchors
    ]
    point_paths = edge_router.route_edges(core_anchors)

    return [
        EdgePath(
            start=start,
            end=end,
            directed_points=[(Point(x=x, y=y), direction) for (x, y, direction) in path],
        )
        for (start, end, _, _), path in zip(edge_anchors, point_paths)
    ]
