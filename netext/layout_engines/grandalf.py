from collections.abc import Hashable
from typing import Any

from grandalf.graphs import Edge, Vertex, Graph  # type: ignore
from grandalf.layouts import SugiyamaLayout  # type: ignore

from netext.geometry.point import FloatPoint  # type: ignore

from .engine import G, LayoutEngine


class GrandalfView:
    w = 0
    h = 0
    xy = (0, 0)


def _create_vertex(node: Hashable, data: dict[str, Any]) -> Vertex:
    v = Vertex(node)

    # The API is a bit weird that it assumes to just add some members externally.
    v.view = GrandalfView()
    v.view.w = data["_netext_node_buffer"].layout_width * 5
    v.view.h = data["_netext_node_buffer"].layout_height * 5
    return v


class GrandalfSugiyamaLayout(LayoutEngine[G]):
    """Layout engine that uses the grandalf library to layout the graph using the Sugiyama algorithm.

    Multiple components will be placed next to each other.
    """

    def __call__(self, g: G) -> dict[Hashable, FloatPoint]:
        vertices = {
            node: _create_vertex(node, data) for node, data in g.nodes(data=True)
        }
        edges = [Edge(vertices[u], vertices[v]) for u, v in g.edges]
        graph = Graph(vertices.values(), edges)

        # TODO Open up settings to netext
        for c in graph.components():
            sug = SugiyamaLayout(c)
            sug.init_all()
            sug.draw(3)
        # Rescale back, but leave a bit more space to avoid overlaps in the
        # terminal coordinate space.
        result = dict()
        x_offset = 0
        for c in graph.components():
            component = {
                v.data: FloatPoint(x=v.view.xy[0] / 4 + x_offset, y=v.view.xy[1] / 6)
                for v in c.sV
            }
            x_offset = max([v.view.xy[0] / 4 + x_offset + v.view.w + 2 for v in c.sV])
            result.update(component)
        return result
