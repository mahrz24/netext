from collections.abc import Hashable
import netext._core as core
from netext._core import DirectedPoint, Point
from netext.edge_routing.edge import EdgePath
from netext.edge_routing.modes import EdgeRoutingMode
from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text


def _edge_routing_mode_to_routing_config(edge_routing_mode: EdgeRoutingMode) -> core.RoutingConfig:
    match edge_routing_mode:
        case EdgeRoutingMode.ORTHOGONAL:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.ORTHOGONAL,
                generate_trace=True,
            )
        case _:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.MOORE,
                generate_trace=True,
            )


def route_edge(
    u: Hashable,
    v: Hashable,
    start: DirectedPoint,
    end: DirectedPoint,
    edge_router: core.EdgeRouter,
    edge_routing_mode: EdgeRoutingMode,
) -> EdgePath:
    result = edge_router.route_edge(
        u,
        v,
        start,
        end,
        start,
        end,
        config=_edge_routing_mode_to_routing_config(edge_routing_mode),
    )
    path = result.path

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
    result = edge_router.route_edges(core_anchors)

    point_paths = result.paths

    return [
        EdgePath(
            start=start.point,
            end=end.point,
            directed_points=path,
        )
        for (_, _, start, end, _), path in zip(edge_anchors, point_paths)
    ]
