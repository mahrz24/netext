from typing import Any, Dict, Hashable

from grandalf.graphs import Edge, Vertex, graph_core
from grandalf.layouts import SugiyamaLayout

from .engine import G, LayoutEngine


class GrandalfView:
    w = 0
    h = 0
    xy = (0, 0)


def _create_vertex(node: Hashable, data: Dict[Hashable, Any]) -> Vertex:
    v = Vertex(node)

    # The API is a bit weird that it assumes to just add some members externally.
    v.view = GrandalfView()  # type: ignore
    # TODO: A width of 1 does not work well and makes to much space, so we scale up by some arbitrary constant
    v.view.w = data["_netext_node_buffer"].width * 5  # type: ignore
    v.view.h = data["_netext_node_buffer"].height * 5  # type: ignore
    return v


# TODO: Add proper typing here
class GrandalfSugiyamaLayout(LayoutEngine[G]):
    def __call__(self, g: G):
        vertices = {
            node: _create_vertex(node, data) for node, data in g.nodes(data=True)
        }
        edges = [Edge(vertices[u], vertices[v]) for u, v in g.edges]
        graph = graph_core(vertices.values(), edges)

        sug = SugiyamaLayout(graph)
        sug.init_all(roots=[vertices[0]])
        sug.draw(3)
        # Rescale back, but leave a bit more space to avoid overlaps in the
        # terminal coordinate space.
        return {v.data: (v.view.xy[0] / 4, v.view.xy[1] / 6) for v in graph.sV}  # type: ignore
