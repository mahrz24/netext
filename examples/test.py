from netext import TerminalGraph
from rich import print
from rich.panel import Panel
from netext.terminal_graph import TerminalGraph
from networkx import binomial_tree

g = binomial_tree(4)

print(Panel(TerminalGraph(g), title="Binomial Tree", expand=False))
