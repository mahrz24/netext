from collections.abc import Hashable
from typing import Any

from grandalf.graphs import Edge, Vertex, Graph  # type: ignore
from grandalf.layouts import SugiyamaLayout  # type: ignore

from .engine import G, LayoutEngine


class GrandalfView:
    w = 0
    h = 0
    xy = (0, 0)


def _create_vertex(node: Hashable, data: dict[Hashable, Any]) -> Vertex:
    v = Vertex(node)

    # The API is a bit weird that it assumes to just add some members externally.
    v.view = GrandalfView()
    # TODO: A width of 1 does not work well and makes to much space, so we scale up by some arbitrary constant
    v.view.w = data["_netext_node_buffer"].width * 5
    v.view.h = data["_netext_node_buffer"].height * 5
    return v


# TODO: Add proper typing here
class GrandalfSugiyamaLayout(LayoutEngine[G]):
    def __call__(self, g: G) -> dict[Hashable, tuple[float, float]]:
        vertices = {
            node: _create_vertex(node, data) for node, data in g.nodes(data=True)
        }
        edges = [Edge(vertices[u], vertices[v]) for u, v in g.edges]
        graph = Graph(vertices.values(), edges)

        # TODO Open up settings to netext
        # TODO Draw components next to each other.
        for c in graph.components():
            sug = SugiyamaLayout(c)
            sug.init_all()
            sug.draw(3)
        # Rescale back, but leave a bit more space to avoid overlaps in the
        # terminal coordinate space.
        vs = []
        for c in graph.components():
            vs.extend(c.sV)
        return {v.data: (v.view.xy[0] / 4, v.view.xy[1] / 6) for v in vs}
