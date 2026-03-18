# Tutorial

## First Steps

To render a graph, create a [netext.ConsoleGraph][] with nodes and edges, then print it:

```python
from netext import ConsoleGraph
from rich import print

g = ConsoleGraph(
    nodes={"Hello": {}, "World": {}},
    edges=[("Hello", "World")],
)

print(g)
```

```{.rich title='Hello World' }
from netext import ConsoleGraph
from rich import print

output = ConsoleGraph(
    nodes={"Hello": {}, "World": {}},
    edges=[("Hello", "World")],
)
```

### Using networkx

If you already have a [networkx](https://networkx.org/) graph, use the `from_networkx` classmethod:

```python
from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

print(ConsoleGraph.from_networkx(g))
```

```{.rich title='Hello World (networkx)' }
from netext import ConsoleGraph
from rich import print

import networkx as nx
g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

output = ConsoleGraph.from_networkx(g)
```

## A Styled Graph

You can easily style the graph by adding attributes to the nodes and edges (see the [user guide about styling](./user-guide/styling-graphs.md)):

```python
import networkx as nx
from rich.style import Style
from rich import box, print

from netext import ConsoleGraph, EdgeRoutingMode

g = nx.binomial_tree(3)

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, Style(color="red"), "$style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")

nx.set_edge_attributes(g, Style(color="green"), "$style")

print(ConsoleGraph.from_networkx(g))
```


```{.rich title='Binomial Tree' }
import networkx as nx
from rich.style import Style
from rich import box

from netext import ConsoleGraph, EdgeRoutingMode

g = nx.binomial_tree(3)

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, Style(color="red"), "$style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")

nx.set_edge_attributes(g, Style(color="green"), "$style")

output = ConsoleGraph.from_networkx(g)
```
