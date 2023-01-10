from typing import cast

import networkx as nx
from rich import box, print
from rich.panel import Panel
from rich.pretty import Pretty
from rich.style import Style
from rich.table import Table

from netext import TerminalGraph
from netext.edge_rasterizer import EdgeRoutingMode

g = cast(nx.Graph, nx.binomial_tree(5))
g1 = cast(nx.DiGraph, nx.paley_graph(5))


def _render(n, d, s):
    t = Table(title=n)

    t.add_column("Key")
    t.add_column("Val")

    for key, val in d.items():
        t.add_row(key, Pretty(val))

    return t


nx.set_node_attributes(g1, "none", "$shape")
nx.set_node_attributes(g1, _render, "$node-renderer")
nx.set_node_attributes(g, Style(color="blue"), "$text-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")

nx.set_edge_attributes(g, EdgeRoutingMode.straight, "$edge-routing-mode")


print(Panel(TerminalGraph(g), title="Binomial Tree", expand=False))
print(Panel(TerminalGraph(g1), title="Payley Graph", expand=False))
