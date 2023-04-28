from typing import Hashable
from netext.layout_engines.engine import LayoutEngine, G


class StaticLayout(LayoutEngine[G]):
    """Static layout engine that uses the `$x` and `$y` attributes of the nodes."""

    def __call__(self, graph: G) -> dict[Hashable, tuple[float, float]]:
        return {
            n: (d.get("$x", 0), d.get("$y", 0)) for (n, d) in graph.nodes(data=True)
        }
