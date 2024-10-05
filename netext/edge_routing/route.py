from collections.abc import Hashable
import netext._core as core
from netext._core import DirectedPoint, Direction, Point
from netext.edge_routing.edge import EdgePath
from netext.edge_routing.modes import EdgeRoutingMode

def _edge_routing_mode_to_routing_config(
    edge_routing_mode: EdgeRoutingMode
) -> core.RoutingConfig:
    match edge_routing_mode:
        case EdgeRoutingMode.ORTHOGONAL:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.ORTHOGONAL,
                corner_cost=1,
                diagonal_cost=100,
                line_cost=10,
                shape_cost=5,
            )
        case _:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.MOORE,
                corner_cost=0,
                diagonal_cost=0,
                line_cost=10,
                shape_cost=5,
            )

def route_edge(
    start: Point,
    end: Point,
    start_direction: Direction,
    end_direction: Direction,
    edge_router: core.EdgeRouter,
    edge_routing_mode: EdgeRoutingMode,
) -> EdgePath:
    path = edge_router.route_edge(
        start=core.Point(x=start.x, y=start.y),
        end=core.Point(x=end.x, y=end.y),
        start_direction=start_direction,
        end_direction=end_direction,
        config=_edge_routing_mode_to_routing_config(edge_routing_mode),
    )

    return EdgePath(
        start=start,
        end=end,
        directed_points=[DirectedPoint(x=x, y=y, direction=direction) for (x, y, direction) in path],
    )


def route_edges(
    edge_router: core.EdgeRouter, edge_anchors: list[tuple[Hashable, Hashable, Point, Point, Direction, Direction, EdgeRoutingMode]]
) -> list[EdgePath]:
    core_anchors = [
        (
            u,
            v,
            core.Point(x=start.x, y=start.y),
            core.Point(x=end.x, y=end.y),
            start_direction,
            end_direction,
            _edge_routing_mode_to_routing_config(edge_routing_mode),
        )
        for u, v, start, end, start_direction, end_direction, edge_routing_mode in edge_anchors
    ]
    point_paths = edge_router.route_edges(core_anchors)

    return [
        EdgePath(
            start=start,
            end=end,
            directed_points=path,
        )
        for (_, _, start, end, _, _, _), path in zip(edge_anchors, point_paths)
    ]
