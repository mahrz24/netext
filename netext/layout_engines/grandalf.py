import typing
from typing import Hashable, Dict, Any
from .engine import LayoutEngine
from grandalf.graphs import Vertex,Edge,Graph,graph_core
from grandalf.layouts import SugiyamaLayout

class GrandalfView:
    w = 0
    h = 0
    xy = (0, 0)


def _create_vertex(node: Hashable, data: Dict[Hashable, Any]) -> Vertex:
    v = Vertex(node)
    v.view = GrandalfView()
    v.view.w = data["_netext_node_buffer"].width
    v.view.h = data["_netext_node_buffer"].height
    return v


# TODO: Add proper typing here
class GrandalfSugiyamaLayout(LayoutEngine):
    def __call__(self, g):
        vertices = {node: _create_vertex(node, data) for node, data in g.nodes(data=True)}
        edges = [Edge(vertices[u], vertices[v]) for u,v in g.edges]
        graph = graph_core(vertices.values(), edges)

        sug = SugiyamaLayout(graph)
        sug.init_all(roots=[vertices[0]])
        sug.draw(3)
        return {v.data: v.view.xy for v in graph.sV}
