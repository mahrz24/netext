from heapq import heappush
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
    # Get the offset and maximum dimension that needs to be supported by the edge.
    x_offset = min(start.x, end.x, start_helper.x, end_helper.x, *map(lambda n: n.x, all_nodes), *map(lambda e: e.start.x, routed_edges), *map(lambda e: e.end.x, routed_edges))
