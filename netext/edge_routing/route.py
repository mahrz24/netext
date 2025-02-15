from collections.abc import Hashable
import netext._core as core
from netext._core import DirectedPoint
from netext.edge_routing.edge import EdgePath
from netext.edge_routing.modes import EdgeRoutingMode


def _edge_routing_mode_to_routing_config(edge_routing_mode: EdgeRoutingMode) -> core.RoutingConfig:
    match edge_routing_mode:
        case EdgeRoutingMode.ORTHOGONAL:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.ORTHOGONAL,
                corner_cost=10,
                diagonal_cost=1000,
                line_cost=20,
                shape_cost=150,
                direction_change_margin=1,
            )
        case _:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.MOORE,
                corner_cost=0,
                diagonal_cost=0,
                line_cost=50,
                shape_cost=150,
                direction_change_margin=1,
            )


def route_edge(
    start: DirectedPoint,
    end: DirectedPoint,
    edge_router: core.EdgeRouter,
    edge_routing_mode: EdgeRoutingMode,
) -> EdgePath:
    path = edge_router.route_edge(
        start,
        end,
        config=_edge_routing_mode_to_routing_config(edge_routing_mode),
    )

    return EdgePath(
        start=start.point,
        end=end.point,
        directed_points=path,
    )


def route_edges(
    edge_router: core.EdgeRouter,
    edge_anchors: list[tuple[Hashable, Hashable, DirectedPoint, DirectedPoint, EdgeRoutingMode]],
) -> list[EdgePath]:
    core_anchors = [
        (
            u,
            v,
            start,
            end,
            _edge_routing_mode_to_routing_config(edge_routing_mode),
        )
        for u, v, start, end, edge_routing_mode in edge_anchors
    ]
    point_paths = edge_router.route_edges(core_anchors)

    return [
        EdgePath(
            start=start.point,
            end=end.point,
            directed_points=path,
        )
        for (_, _, start, end, _), path in zip(edge_anchors, point_paths)
    ]
