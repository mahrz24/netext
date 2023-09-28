# Tutorial

## First Steps

To render a graph, you first need to create a [networkx](https://networkx.org/) graph. Once it's there,
the netext API is very simple. Just wrap it in a [netext.ConsoleGraph][] object
and render it

```python
from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

print(ConsoleGraph(g))
```

```{.rich title='Hello World' }
from netext import ConsoleGraph
from rich import print

import networkx as nx
g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

output = ConsoleGraph(g)
```

## A Styled Graph

You can easily style the graph by adding attributes to the nodes and edges (see the [user guide about styling](./user-guide/styling-graphs.md)):

```python
import networkx as nx
from rich.style import Style
from rich import box, print

from netext import ConsoleGraph
from netext.edge_rasterizer import EdgeRoutingMode

g = nx.binomial_tree(3)

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, Style(color="red"), "$style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")

nx.set_edge_attributes(g, Style(color="green"), "$style")

print(ConsoleGraph(g))
```


```{.rich title='Binomial Tree' }
import networkx as nx
from rich.style import Style
from rich import box

from netext import ConsoleGraph
from netext.edge_rasterizer import EdgeRoutingMode

g = nx.binomial_tree(3)

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, Style(color="red"), "$style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")

nx.set_edge_attributes(g, Style(color="green"), "$style")

output = ConsoleGraph(g)
```
