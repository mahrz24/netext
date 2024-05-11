from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.DiGraph()
g.add_node(0)
g.add_node(1)
g.add_edge(0, 1)

print(ConsoleGraph(g))

g = nx.DiGraph()
g.add_node(0)
g.add_node(1)
g.add_node(2)
g.add_edge(0, 1)
g.add_edge(0, 2)

print(ConsoleGraph(g))

g = nx.DiGraph()
g.add_node(0)
g.add_node(1)
g.add_node(2)
g.add_edge(0, 1)
g.add_edge(0, 2)
g.add_edge(1, 2)

print(ConsoleGraph(g))

g = nx.DiGraph()
g.add_node(0)
g.add_node(1)
g.add_node(2)
g.add_node(3)
g.add_node(4)


g.add_edge(0, 1)
g.add_edge(0, 2)
g.add_edge(0, 3)

g.add_edge(1, 2)
g.add_edge(2, 3)

g.add_edge(1, 3)
g.add_edge(1, 4)

print(ConsoleGraph(g))
