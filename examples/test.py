from typing import cast

import networkx as nx
from rich import box, print
from rich.panel import Panel
from rich.style import Style

from netext import TerminalGraph

g = cast(nx.Graph, nx.binomial_tree(4))
g1 = cast(nx.DiGraph, nx.paley_graph(5))

nx.set_node_attributes(g1, "none", "$shape")
nx.set_node_attributes(g, Style(color="blue"), "$text-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")


print(Panel(TerminalGraph(g), title="Binomial Tree", expand=False))
print(Panel(TerminalGraph(g1), title="Payley Graph", expand=False))
