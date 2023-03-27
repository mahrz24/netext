from typing import cast

import networkx as nx
from rich import box, print
from rich.panel import Panel
from rich.pretty import Pretty
from rich.style import Style
from rich.table import Table

from netext import TerminalGraph
from netext.edge_rasterizer import ArrowTip, EdgeRoutingMode, EdgeSegmentDrawingMode
from netext.node_rasterizer import JustContent

g = cast(nx.Graph, nx.binomial_tree(5))
g1 = cast(nx.DiGraph, nx.paley_graph(5))


def _render(n, d, s):
    t = Table(title=n)

    t.add_column("Key")
    t.add_column("Val")

    for key, val in d.items():
        t.add_row(key, Pretty(val))

    return t


nx.set_node_attributes(g1, JustContent(), "$shape")
nx.set_node_attributes(g1, _render, "$content-renderer")


def _render2(n, d, s):
    return f"#N{n}"


g.add_edge(16, 0)
# g.add_edge(16, 30)

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")
nx.set_edge_attributes(g, EdgeRoutingMode.orthogonal, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.box, "$edge-segment-drawing-mode")
nx.set_edge_attributes(g, ArrowTip.arrow, "$end-arrow-tip")
nx.set_edge_attributes(g, ArrowTip.arrow, "$start-arrow-tip")

# nx.set_edge_attributes(g, "foo", "$label")
nx.set_node_attributes(g, _render2, "$content-renderer")


print(Panel(TerminalGraph(g), title="Binomial Tree", expand=False))
print(Panel(TerminalGraph(g1), title="Payley Graph", expand=False))
