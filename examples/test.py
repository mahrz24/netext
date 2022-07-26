from networkx import binomial_tree, paley_graph
from rich import print
from rich.panel import Panel

from netext import TerminalGraph
from netext.terminal_graph import TerminalGraph

g = binomial_tree(4)
g1 = paley_graph(5)

print(Panel(TerminalGraph(g), title="Binomial Tree", expand=False))
print(Panel(TerminalGraph(g1), title="Payley Graph", expand=False))
