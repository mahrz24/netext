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
                corner_cost=50,
                diagonal_cost=0,
                line_cost=90,
                shape_cost=90,
                direction_change_margin_start=1,
                direction_change_margin_end=1,
                generate_trace=True,
            )
        case _:
            return core.RoutingConfig(
                neighborhood=core.Neighborhood.MOORE,
                corner_cost=0,
                diagonal_cost=0,
                line_cost=10,
                shape_cost=50,
                direction_change_margin_start=2,
                direction_change_margin_end=2,
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


    if result.trace is not None:
        console = Console()
        for (ecm, path) in zip(result.trace.edge_cost_maps, result.paths):
            undirected_points = [dp.point for dp in path]
            print(f"Edge cost map for edge {ecm[0]} -> {ecm[1]}:")
            min_x = min(x for x, _ in result.trace.edge_cost_maps[ecm].keys())
            max_x = max(x for x, _ in result.trace.edge_cost_maps[ecm].keys())
            min_y = min(y for _, y in result.trace.edge_cost_maps[ecm].keys())
            max_y = max(y for _, y in result.trace.edge_cost_maps[ecm].keys())
            max_cost = max(result.trace.edge_cost_maps[ecm].values(), default=0)
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    cost = result.trace.edge_cost_maps[ecm].get((x, y), 0)
                    char = " "
                    if Point(x,y) in undirected_points:
                        char = "x"
                    console.print(
                        Text(char, style=Style(bgcolor=Color.from_rgb(cost / max_cost * 255, 150, 150))), end=""
                    )
                console.print("")
    point_paths = result.paths

    return [
        EdgePath(
            start=start.point,
            end=end.point,
            directed_points=path,
        )
        for (_, _, start, end, _), path in zip(edge_anchors, point_paths)
    ]
