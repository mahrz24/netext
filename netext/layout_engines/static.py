from typing import Hashable
from netext.geometry.point import FloatPoint
from netext.layout_engines.engine import LayoutEngine, G


class StaticLayout(LayoutEngine[G]):
    """Static layout engine that uses the `$x` and `$y` attributes of the nodes."""

    def __call__(self, graph: G) -> dict[Hashable, FloatPoint]:
        return {
            n: FloatPoint(x=d.get("$x", 0), y=d.get("$y", 0))
            for (n, d) in graph.nodes(data=True)
        }
